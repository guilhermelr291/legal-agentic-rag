"""Document processing orchestrator for the ingestion pipeline.

Coordinates the full document processing workflow:
1. Download file from Supabase Storage
2. Route to appropriate processor based on file type
3. Extract text/metadata, chunk, generate embeddings
4. Update document status with stage tracking
5. Trigger async graph indexing (when enabled)
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

from my_agent.config.settings import get_settings
from services.chunking.legal_chunker import LegalChunker
from services.db.graph_repository import GraphRepository
from services.db.repositories import ChunkRepository, DocumentRepository, DocumentRecord
from services.embeddings.generator import EmbeddingGenerator
from services.extractors.base import ExtractionResult
from services.extractors.docx_extractor import DOCXExtractor
from services.extractors.pdf_extractor import PDFExtractor
from services.extractors.xlsx_extractor import XLSXMetadataExtractor
from services.graph.extractor import GraphExtractor
from services.storage.supabase_client import StorageError, SupabaseClient

logger = logging.getLogger(__name__)

# Constants
STORAGE_BUCKET = "documents"
MAX_FILE_SIZE_MB = 50
GRAPH_INDEXING_TIMEOUT_SECONDS = 60  # Max time for graph indexing before timeout


class DocumentProcessorError(Exception):
    """Exception for document processing errors."""

    def __init__(
        self,
        message: str,
        stage: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.original_error = original_error


class DocumentProcessor:
    """Main pipeline coordinator for document ingestion.

    Orchestrates the full processing workflow from download to ready status,
    routing files to appropriate processors based on type (PDF/DOCX vs XLSX).
    Supports optional async graph indexing for Graph RAG when enabled.

    Usage:
        >>> from services.storage.supabase_client import SupabaseClient
        >>> from services.db.repositories import DocumentRepository, ChunkRepository
        >>> from services.db.graph_repository import GraphRepository
        >>> from services.embeddings.generator import EmbeddingGenerator
        >>> from services.graph.extractor import GraphExtractor
        >>>
        >>> client = await SupabaseClient.from_service_role()
        >>> doc_repo = DocumentRepository(client)
        >>> chunk_repo = ChunkRepository(client)
        >>> graph_repo = GraphRepository(client)
        >>> embed_gen = EmbeddingGenerator()
        >>> graph_extractor = GraphExtractor(enabled=get_settings().graph_rag_enabled)
        >>>
        >>> processor = DocumentProcessor(
        ...     storage_client=client,
        ...     document_repo=doc_repo,
        ...     chunk_repo=chunk_repo,
        ...     embedding_generator=embed_gen,
        ...     graph_extractor=graph_extractor,
        ...     graph_repository=graph_repo,
        ... )
        >>> await processor.process(document_id="uuid", user_id="user_uuid")
    """

    def __init__(
        self,
        storage_client: SupabaseClient,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        embedding_generator: EmbeddingGenerator,
        chunker: LegalChunker | None = None,
        graph_extractor: GraphExtractor | None = None,
        graph_repository: GraphRepository | None = None,
    ) -> None:
        """Initialize the document processor with all dependencies.

        Args:
            storage_client: Supabase client for storage operations
            document_repo: Repository for document records
            chunk_repo: Repository for chunk records
            embedding_generator: Generator for embeddings
            chunker: Optional custom chunker (uses default if None)
            graph_extractor: Optional graph extractor for Graph RAG indexing
            graph_repository: Optional graph repository for persisting nodes/edges
        """
        self._storage = storage_client
        self._doc_repo = document_repo
        self._chunk_repo = chunk_repo
        self._embed_gen = embedding_generator
        self._chunker = chunker or LegalChunker()
        self._graph_extractor = graph_extractor
        self._graph_repo = graph_repository

        # Initialize extractors
        self._pdf_extractor = PDFExtractor()
        self._docx_extractor = DOCXExtractor()
        self._xlsx_extractor = XLSXMetadataExtractor()

        # Check if graph indexing is enabled via settings
        self._graph_enabled = (
            graph_extractor is not None
            and graph_repository is not None
            and get_settings().graph_rag_enabled
        )

    async def process(self, document_id: str, user_id: str) -> None:
        """Main entry point for document processing.

        Downloads the file from storage, routes to appropriate processor,
        and updates status at each stage. All errors are caught and
        result in status='failed' with error_msg set.

        Args:
            document_id: UUID of the document to process
            user_id: User ID for RLS enforcement

        Raises:
            DocumentProcessorError: Only for unexpected errors;
                normal processing errors update document status instead
        """
        logger.info("Starting document processing: %s", document_id)

        try:
            # Fetch document record
            doc = await self._doc_repo.get_by_id(document_id, user_id)
            if not doc:
                raise DocumentProcessorError(
                    f"Document not found: {document_id}",
                    stage="init",
                )

            # Download file from storage
            download_start = time.monotonic()
            temp_path = await self._download_file(doc)
            download_duration = time.monotonic() - download_start
            logger.info(
                "Downloaded file in %.2fs: %s",
                download_duration,
                doc.storage_path,
            )

            try:
                # Route to appropriate processor
                if doc.file_type in ("pdf", "docx"):
                    await self._process_pdf_docx(doc, temp_path, user_id)
                elif doc.file_type == "xlsx":
                    await self._process_xlsx(doc, temp_path, user_id)
                else:
                    raise DocumentProcessorError(
                        f"Unsupported file type: {doc.file_type}",
                        stage="routing",
                    )

            finally:
                # Clean up temp file
                self._cleanup_temp_file(temp_path)

        except DocumentProcessorError as e:
            # Known processing error - update status
            logger.error(
                "Document processing failed at stage '%s': %s",
                e.stage,
                e,
            )
            await self._set_failed_status(document_id, user_id, str(e))

        except Exception as e:
            # Unexpected error - wrap and update status
            logger.exception("Unexpected error processing document: %s", document_id)
            await self._set_failed_status(
                document_id,
                user_id,
                f"Processing failed: {str(e)}",
            )
            raise DocumentProcessorError(
                f"Unexpected error: {e}",
                stage="unknown",
                original_error=e,
            ) from e

    async def _download_file(self, doc: DocumentRecord) -> Path:
        """Download file from Supabase Storage to temp location.

        Args:
            doc: Document record with storage_path

        Returns:
            Path to downloaded temp file

        Raises:
            DocumentProcessorError: If download fails
        """
        try:
            file_data = await self._storage.download_file(
                bucket_name=STORAGE_BUCKET,
                file_path=doc.storage_path,
            )

            # Create temp file with appropriate suffix
            suffix = f".{doc.file_type}"
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as temp_file:
                temp_file.write(file_data)
                temp_path = Path(temp_file.name)

            logger.debug("Downloaded to temp file: %s", temp_path)
            return temp_path

        except StorageError as e:
            raise DocumentProcessorError(
                f"Failed to download file: {e}",
                stage="download",
                original_error=e,
            ) from e
        except Exception as e:
            raise DocumentProcessorError(
                f"Download failed: {e}",
                stage="download",
                original_error=e,
            ) from e

    def _cleanup_temp_file(self, temp_path: Path) -> None:
        """Remove temporary file if it exists.

        Args:
            temp_path: Path to temp file
        """
        try:
            if temp_path.exists():
                os.unlink(temp_path)
                logger.debug("Cleaned up temp file: %s", temp_path)
        except Exception as e:
            logger.warning("Failed to clean up temp file %s: %s", temp_path, e)

    async def _set_failed_status(
        self,
        document_id: str,
        user_id: str,
        error_msg: str,
    ) -> None:
        """Update document status to failed.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            error_msg: Error message to store
        """
        try:
            await self._doc_repo.update_status(
                document_id=document_id,
                status="failed",
                error_msg=error_msg,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(
                "Failed to update document status to failed: %s - %s",
                document_id,
                e,
            )

    async def _process_pdf_docx(
        self,
        doc: DocumentRecord,
        file_path: Path,
        user_id: str,
    ) -> None:
        """Process PDF or DOCX file: extract → chunk → embed → ready.

        Args:
            doc: Document record
            file_path: Path to temp file
            user_id: User ID for RLS

        Raises:
            DocumentProcessorError: If any stage fails
        """
        logger.info("Processing PDF/DOCX: %s", doc.filename)

        # Stage 1: Extract text
        extract_start = time.monotonic()
        extraction = await self._extract_text(doc.file_type, str(file_path))
        extract_duration = time.monotonic() - extract_start
        logger.info(
            "Extraction complete in %.2fs: %d chars, %d pages",
            extract_duration,
            len(extraction.text),
            len(extraction.pages),
        )

        if not extraction.success:
            raise DocumentProcessorError(
                extraction.error or "Text extraction failed",
                stage="extraction",
            )

        if not extraction.text.strip():
            raise DocumentProcessorError(
                "Document contains no extractable text",
                stage="extraction",
            )

        # Stage 2: Chunk
        chunk_start = time.monotonic()
        chunks = self._chunker.chunk(extraction.text, extraction.pages)
        chunk_duration = time.monotonic() - chunk_start
        logger.info(
            "Chunking complete in %.2fs: %d chunks created",
            chunk_duration,
            len(chunks),
        )

        if not chunks:
            raise DocumentProcessorError(
                "Document contains no extractable text",
                stage="chunking",
            )

        # Stage 3: Generate embeddings and upsert
        embed_start = time.monotonic()
        stats = await self._embed_gen.generate_and_upsert(
            document_id=doc.id,
            user_id=user_id,
            chunks=chunks,
            chunk_repo=self._chunk_repo,
        )
        embed_duration = time.monotonic() - embed_start
        logger.info(
            "Embedding generation complete in %.2fs: %s",
            embed_duration,
            stats.to_dict(),
        )

        if stats.errors > 0 and stats.embeddings_generated == 0:
            raise DocumentProcessorError(
                "All embeddings failed to generate",
                stage="embedding",
            )

        # Stage 4: Update status to ready
        await self._doc_repo.update_status(
            document_id=doc.id,
            status="ready",
            user_id=user_id,
        )
        logger.info(
            "Document processing complete: %s (total time: %.2fs)",
            doc.id,
            extract_duration + chunk_duration + embed_duration,
        )

        # Stage 5: Trigger async graph indexing (non-blocking)
        # This runs in the background and doesn't affect document status
        self._trigger_graph_indexing(doc.id, user_id, chunks)

    async def _process_xlsx(
        self,
        doc: DocumentRecord,
        file_path: Path,
        user_id: str,
    ) -> None:
        """Process XLSX file: extract metadata only → ready.

        XLSX files skip chunking and embeddings; only metadata is extracted
        and stored in documents.meta for the XLSX tool to use.

        Args:
            doc: Document record
            file_path: Path to temp file
            user_id: User ID for RLS

        Raises:
            DocumentProcessorError: If metadata extraction fails
        """
        logger.info("Processing XLSX: %s", doc.filename)

        # Extract metadata
        extract_start = time.monotonic()
        metadata = self._xlsx_extractor.extract(str(file_path))
        extract_duration = time.monotonic() - extract_start
        logger.info(
            "XLSX metadata extraction complete in %.2fs: %d sheets",
            extract_duration,
            metadata.total_sheets,
        )

        if not metadata.success:
            raise DocumentProcessorError(
                metadata.error or "XLSX metadata extraction failed",
                stage="extraction",
            )

        # Prepare metadata update
        meta_update: dict[str, Any] = {
            "xlsx_metadata": {
                "sheet_names": metadata.sheet_names,
                "sheets": metadata.sheets,
                "total_sheets": metadata.total_sheets,
            }
        }

        # Persist metadata to documents.meta
        await self._doc_repo.update_meta(
            document_id=doc.id,
            meta=meta_update,
            user_id=user_id,
        )

        # Update document status to ready
        await self._doc_repo.update_status(
            document_id=doc.id,
            status="ready",
            user_id=user_id,
        )

        logger.info(
            "XLSX processing complete: %s (time: %.2fs)",
            doc.id,
            extract_duration,
        )

    async def _extract_text(
        self,
        file_type: Literal["pdf", "docx"],
        file_path: str,
    ) -> ExtractionResult:
        """Extract text from PDF or DOCX file.

        Args:
            file_type: Type of file
            file_path: Path to file

        Returns:
            ExtractionResult with text, pages, and metadata

        Raises:
            DocumentProcessorError: If file type is unsupported
        """
        if file_type == "pdf":
            return self._pdf_extractor.extract(file_path)
        else:  # docx
            return self._docx_extractor.extract(file_path)

    async def _update_graph_status(
        self,
        document_id: str,
        user_id: str,
        status: Literal["processing", "ready", "failed", "timeout", "ready_empty"],
        error_msg: str | None = None,
    ) -> None:
        """Update graph_status in documents.meta.

        Graph status is tracked separately from document status to allow
        graceful degradation when graph indexing fails.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            status: Graph status value
            error_msg: Optional error message for failed/timeout status
        """
        try:
            meta_update: dict[str, Any] = {"graph_status": status}
            if error_msg:
                meta_update["graph_error"] = error_msg

            await self._doc_repo.update_meta(
                document_id=document_id,
                meta=meta_update,
                user_id=user_id,
            )
            logger.info(
                "Updated graph_status to '%s' for document: %s",
                status,
                document_id,
            )
        except Exception as e:
            # Graph status updates should never fail the document
            logger.warning(
                "Failed to update graph_status for document %s: %s",
                document_id,
                e,
            )

    async def _run_graph_indexing(
        self,
        document_id: str,
        user_id: str,
        chunks: list[Any],
    ) -> None:
        """Run graph indexing with timeout handling.

        Extracts nodes and edges from chunks and persists to graph storage.
        Updates graph_status throughout the process. Errors are caught
        and logged without affecting document status.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            chunks: Legal chunks extracted from document
        """
        if not self._graph_enabled or not self._graph_extractor or not self._graph_repo:
            logger.debug("Graph indexing skipped: not enabled or missing dependencies")
            return

        logger.info(
            "Starting graph indexing for document: %s (%d chunks)",
            document_id,
            len(chunks),
        )

        # Mark graph as processing
        await self._update_graph_status(document_id, user_id, "processing")

        try:
            # Run extraction with timeout
            extraction_task = self._graph_extractor.extract(
                document_id=document_id,
                user_id=user_id,
                chunks=chunks,
            )

            result = await asyncio.wait_for(
                extraction_task,
                timeout=GRAPH_INDEXING_TIMEOUT_SECONDS,
            )

            # Persist nodes and edges if any were extracted
            if result.nodes and result.edges:
                await self._graph_repo.upsert_nodes(result.nodes)
                await self._graph_repo.upsert_edges(result.edges)

                logger.info(
                    "Graph indexing complete: %d nodes, %d edges for document: %s",
                    len(result.nodes),
                    len(result.edges),
                    document_id,
                )

                # Mark as ready or ready_empty based on results
                if len(result.edges) == 0:
                    await self._update_graph_status(
                        document_id, user_id, "ready_empty"
                    )
                else:
                    await self._update_graph_status(document_id, user_id, "ready")
            else:
                logger.info(
                    "Graph indexing returned empty result for document: %s",
                    document_id,
                )
                await self._update_graph_status(document_id, user_id, "ready_empty")

        except asyncio.TimeoutError:
            logger.warning(
                "Graph indexing timed out after %ds for document: %s",
                GRAPH_INDEXING_TIMEOUT_SECONDS,
                document_id,
            )
            await self._update_graph_status(
                document_id,
                user_id,
                "timeout",
                error_msg=f"Graph indexing exceeded {GRAPH_INDEXING_TIMEOUT_SECONDS}s timeout",
            )

        except Exception as e:
            logger.exception(
                "Graph indexing failed for document: %s", document_id
            )
            await self._update_graph_status(
                document_id,
                user_id,
                "failed",
                error_msg=str(e),
            )

    def _trigger_graph_indexing(
        self,
        document_id: str,
        user_id: str,
        chunks: list[Any],
    ) -> None:
        """Trigger graph indexing as a background async task.

        This method schedules graph indexing to run asynchronously without
        blocking the main processing pipeline. Graph errors are handled
        gracefully and don't affect the document's ready status.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            chunks: Legal chunks extracted from document
        """
        if not self._graph_enabled:
            return

        # Create background task for graph indexing
        # This runs independently and doesn't block the caller
        asyncio.create_task(
            self._run_graph_indexing(document_id, user_id, chunks)
        )
        logger.info(
            "Triggered async graph indexing for document: %s", document_id
        )
