"""Document processing orchestrator with constructor injection.

Provides the DocumentProcessor class that coordinates the complete document
processing pipeline: download → extract → chunk → embed → persist.
Uses constructor injection for all dependencies to enable testability.
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from src.documents.exceptions import (
    ChunkingFailedError,
    DatabaseError,
    DocumentProcessingError,
    EmbeddingGenerationError,
    ExtractionFailedError,
    NoTextContentError,
)
from src.documents.models import Chunk, Document
from src.storage.config import storage_settings

if TYPE_CHECKING:
    # Type-only imports to avoid heavy dependencies during test collection
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.chunking.service import ChunkingService, LegalChunk
    from src.embeddings.service import EmbeddingsService
    from src.extractors.service import ExtractionService
    from src.extractors.xlsx import XLSXMetadata
    from src.storage.service import StorageService


logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """Internal dataclass that tracks processing state.

    Attributes:
        document_id: UUID of the document being processed
        user_id: User ID for RLS and isolation
        file_path: Temporary local file path for downloaded document
        extracted_text: Text content extracted from document
        extracted_pages: List of page info (number, start_char, end_char)
        chunks: List of LegalChunk objects for PDF/DOCX
        xlsx_metadata: XLSXMetadata for XLSX files
        stage_timings: Dict of stage names to duration in seconds
        current_stage: Current pipeline stage being executed
    """

    # Required fields
    document_id: str
    user_id: str
    file_path: Path

    # Optional fields with defaults
    extracted_text: str | None = None
    extracted_pages: list[dict] = field(default_factory=list)
    chunks: list[Any] = field(default_factory=list)  # List[LegalChunk] in runtime
    xlsx_metadata: Any | None = None  # XLSXMetadata in runtime
    stage_timings: dict[str, float] = field(default_factory=dict)
    current_stage: str | None = None


class DocumentProcessor:
    """Orchestrates the document processing pipeline.

    Coordinates the complete flow: download → extract → chunk → embed → persist.
    Uses constructor injection for all dependencies to enable testability.

    Args:
        storage: StorageService for downloading files from Supabase
        extraction: ExtractionService for text/metadata extraction
        chunking: ChunkingService for legal document chunking
        embeddings: EmbeddingsService for OpenAI embedding generation
        db: Async SQLAlchemy session for database operations
    """

    def __init__(
        self,
        storage: StorageService,
        extraction: ExtractionService,
        chunking: ChunkingService,
        embeddings: EmbeddingsService,
        db: AsyncSession,
    ) -> None:
        """Initialize processor with all required services."""
        self._storage = storage
        self._extraction = extraction
        self._chunking = chunking
        self._embeddings = embeddings
        self._db = db

    async def process(self, document_id: str, user_id: str) -> None:
        """Process a document through the complete pipeline.

        Args:
            document_id: UUID of the document to process
            user_id: User ID for RLS and isolation

        Updates document status and creates chunks in database.
        All errors are caught, logged, and status is updated to 'failed'.
        """
        logger.info("Starting document processing: %s (user: %s)", document_id, user_id)
        start_time = time.time()

        # Load document and verify status
        result = await self._db.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )
        document = result.scalar_one_or_none()

        if document is None:
            logger.error("Document not found: %s (user: %s)", document_id, user_id)
            raise DocumentProcessingError(
                message=f"Document not found: {document_id}",
                stage="initialization",
                code="DOCUMENT_NOT_FOUND",
            )

        if document.status != "processing":
            logger.error(
                "Document %s has invalid status for processing: %s (expected: processing)",
                document_id,
                document.status,
            )
            raise DocumentProcessingError(
                message=f"Document status is '{document.status}', expected 'processing'",
                stage="initialization",
                code="INVALID_DOCUMENT_STATUS",
            )

        # Determine file extension for temp file
        file_ext = Path(document.filename).suffix or ".tmp"

        # Create temp file and download
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_path = Path(tmp_file.name)

        context: ProcessingContext | None = None
        try:
            # Download stage
            download_start = time.time()
            logger.info("Starting download stage for document: %s", document_id)

            bucket_name = storage_settings.SUPABASE_STORAGE_BUCKET
            await self._storage.download_to_path(
                bucket_name=bucket_name,
                file_path=document.storage_path,
                destination=tmp_path,
            )

            download_duration = time.time() - download_start
            logger.info(
                "Download stage completed for document: %s (duration: %.3fs)",
                document_id,
                download_duration,
            )

            # Create processing context
            context = ProcessingContext(
                document_id=document_id,
                user_id=user_id,
                file_path=tmp_path,
                stage_timings={"download": download_duration},
                current_stage="download",
            )

            # Route to appropriate processor based on file type
            file_type = document.file_type.lower()

            try:
                if file_type in ("pdf", "docx", "doc"):
                    logger.info(
                        "Routing document %s to PDF/DOCX processor (type: %s)",
                        document_id,
                        file_type,
                    )
                    await self._process_pdf_docx(context)
                elif file_type == "xlsx":
                    logger.info(
                        "Routing document %s to XLSX processor",
                        document_id,
                    )
                    await self._process_xlsx(context)
                else:
                    logger.error("Unsupported file type for document %s: %s", document_id, file_type)
                    raise DocumentProcessingError(
                        message=f"Unsupported file type: {file_type}",
                        stage="routing",
                        code="UNSUPPORTED_FILE_TYPE",
                    )
            except DocumentProcessingError:
                # Re-raise specific processing errors to be handled below
                raise
            except Exception as e:
                # Wrap unexpected errors
                logger.exception("Unexpected error processing document: %s", document_id)
                raise DocumentProcessingError(
                    message=f"Unexpected error: {e}",
                    stage=context.current_stage or "unknown",
                    code="PROCESSING_ERROR",
                ) from e

        except DocumentProcessingError as e:
            # Update document status to failed
            logger.error(
                "Document processing failed for %s at stage '%s': %s (code: %s)",
                document_id,
                e.stage,
                e.message,
                e.code,
            )
            try:
                await self._update_document_status_to_failed(
                    document_id, user_id, f"[{e.code}] {e.message}"
                )
            except Exception as status_error:
                logger.exception(
                    "Failed to update error status for document: %s",
                    document_id,
                )
            # Re-raise the original error
            raise

        except Exception:
            # Log unexpected errors
            logger.exception("Unexpected error during document processing: %s", document_id)
            try:
                await self._update_document_status_to_failed(
                    document_id, user_id, "Unexpected processing error"
                )
            except Exception:
                pass
            raise

        finally:
            # Always clean up temp file
            if context is not None:
                self._cleanup_temp_file(context.file_path)
            else:
                # If context wasn't created, cleanup the tmp_path we created
                self._cleanup_temp_file(tmp_path)

            total_duration = time.time() - start_time
            logger.info(
                "Document processing completed for: %s (total duration: %.3fs)",
                document_id,
                total_duration,
            )

    async def _process_pdf_docx(self, context: ProcessingContext) -> None:
        """Process PDF or DOCX file: extract → chunk → embed → persist.

        Args:
            context: ProcessingContext with document information

        Raises:
            ExtractionFailedError: If text extraction fails
            NoTextContentError: If document has no extractable text
            ChunkingFailedError: If chunking fails
            EmbeddingGenerationError: If embedding generation fails
            DatabaseError: If database persistence fails

        Updates:
            - document.status to 'ready' on success
            - document.processed_at timestamp on success
            - context.stage_timings with duration for each stage
        """
        # Stage 1: Extraction
        extraction_start = time.time()
        context.current_stage = "extraction"
        logger.info("Starting extraction stage for document: %s", context.document_id)

        try:
            extraction_result = await self._extraction.extract_text(context.file_path)
        except Exception as e:
            logger.exception("Extraction failed for document: %s", context.document_id)
            raise ExtractionFailedError(message=str(e), file_type=context.file_path.suffix.lstrip(".")) from e

        # Check if extraction reported failure
        if not extraction_result.success:
            logger.error(
                "Extraction failed for document %s: %s",
                context.document_id,
                extraction_result.error,
            )
            raise ExtractionFailedError(
                message=extraction_result.error or "Unknown extraction error",
                file_type=context.file_path.suffix.lstrip("."),
            )

        # Check for empty text content
        if not extraction_result.text or not extraction_result.text.strip():
            logger.error("Document %s has no extractable text", context.document_id)
            raise NoTextContentError()

        extraction_duration = time.time() - extraction_start
        context.stage_timings["extraction"] = extraction_duration
        context.extracted_text = extraction_result.text
        context.extracted_pages = extraction_result.pages
        logger.info(
            "Extraction stage completed for document: %s (duration: %.3fs, pages: %d)",
            context.document_id,
            extraction_duration,
            len(extraction_result.pages),
        )

        # Stage 2: Chunking
        chunking_start = time.time()
        context.current_stage = "chunking"
        logger.info("Starting chunking stage for document: %s", context.document_id)

        try:
            chunks = self._chunking.chunk(extraction_result.text, extraction_result.pages)
        except Exception as e:
            logger.exception("Chunking failed for document: %s", context.document_id)
            raise ChunkingFailedError(message=str(e)) from e

        # Validate chunks were produced
        if not chunks:
            logger.error("Chunking produced no chunks for document: %s", context.document_id)
            raise ChunkingFailedError(message="No chunks produced from document")

        chunking_duration = time.time() - chunking_start
        context.stage_timings["chunking"] = chunking_duration
        context.chunks = chunks
        logger.info(
            "Chunking stage completed for document: %s (duration: %.3fs, chunks: %d)",
            context.document_id,
            chunking_duration,
            len(chunks),
        )

        # Stage 3: Embedding Generation
        embedding_start = time.time()
        context.current_stage = "embedding"
        logger.info("Starting embedding stage for document: %s", context.document_id)

        # Extract text content from chunks for embedding
        chunk_texts = [chunk.content for chunk in chunks]

        try:
            embeddings = await self._embeddings.generate_embeddings(chunk_texts)
        except Exception as e:
            logger.exception("Embedding generation failed for document: %s", context.document_id)
            # Determine batch number from error if available
            batch_number = getattr(e, "batch_number", None)
            raise EmbeddingGenerationError(message=str(e), batch_number=batch_number) from e

        embedding_duration = time.time() - embedding_start
        context.stage_timings["embedding"] = embedding_duration
        logger.info(
            "Embedding stage completed for document: %s (duration: %.3fs, embeddings: %d)",
            context.document_id,
            embedding_duration,
            len(embeddings),
        )

        # Stage 4: Database Persistence (Upsert)
        persistence_start = time.time()
        context.current_stage = "persistence"
        logger.info("Starting persistence stage for document: %s", context.document_id)

        try:
            await self._upsert_chunks(context, chunks, embeddings)
        except Exception as e:
            logger.exception("Database persistence failed for document: %s", context.document_id)
            raise DatabaseError(message=str(e)) from e

        persistence_duration = time.time() - persistence_start
        context.stage_timings["persistence"] = persistence_duration
        logger.info(
            "Persistence stage completed for document: %s (duration: %.3fs)",
            context.document_id,
            persistence_duration,
        )

        # Stage 5: Update Document Status to Ready
        try:
            await self._update_document_status_to_ready(context.document_id, context.user_id)
        except Exception as e:
            logger.exception("Failed to update document status for document: %s", context.document_id)
            raise DatabaseError(message=f"Failed to update document status: {e}") from e

        logger.info(
            "Document processing completed successfully: %s (total stages: %d)",
            context.document_id,
            len(context.stage_timings),
        )

    async def _process_xlsx(self, context: ProcessingContext) -> None:
        """Process XLSX file: extract metadata → persist.

        Args:
            context: ProcessingContext with document information

        Raises:
            ExtractionFailedError: If metadata extraction fails or XLSX is empty/protected
            DatabaseError: If database persistence fails

        Updates:
            - document.status to 'ready' on success
            - document.processed_at timestamp on success
            - document.meta['xlsx_structure'] with sheet/column metadata
            - context.stage_timings with duration for extraction stage
        """
        # Stage 1: Metadata Extraction
        extraction_start = time.time()
        context.current_stage = "extraction"
        logger.info("Starting XLSX metadata extraction for document: %s", context.document_id)

        try:
            xlsx_metadata = await self._extraction.extract_metadata(context.file_path)
        except Exception as e:
            logger.exception("XLSX metadata extraction failed for document: %s", context.document_id)
            raise ExtractionFailedError(message=str(e), file_type="xlsx") from e

        # Check if extraction reported failure
        if not xlsx_metadata.success:
            error_msg = xlsx_metadata.error or "Unknown XLSX extraction error"
            logger.error(
                "XLSX metadata extraction failed for document %s: %s",
                context.document_id,
                error_msg,
            )
            raise ExtractionFailedError(message=error_msg, file_type="xlsx")

        # Check for password-protected XLSX (indicated by specific error patterns)
        if xlsx_metadata.error and ("password" in xlsx_metadata.error.lower() or "protected" in xlsx_metadata.error.lower()):
            logger.error("XLSX is password-protected: %s", context.document_id)
            raise ExtractionFailedError(
                message="XLSX file is password-protected and cannot be processed",
                file_type="xlsx",
            )

        # Validate at least one sheet exists
        if xlsx_metadata.total_sheets == 0 or not xlsx_metadata.sheet_names:
            logger.error("XLSX has no sheets: %s", context.document_id)
            raise ExtractionFailedError(
                message="XLSX file contains no sheets",
                file_type="xlsx",
            )

        extraction_duration = time.time() - extraction_start
        context.stage_timings["extraction"] = extraction_duration
        context.xlsx_metadata = xlsx_metadata
        logger.info(
            "XLSX metadata extraction completed for document: %s (duration: %.3fs, sheets: %d)",
            context.document_id,
            extraction_duration,
            xlsx_metadata.total_sheets,
        )

        # Stage 2: Build and Save XLSX Structure to Document Meta
        persistence_start = time.time()
        context.current_stage = "persistence"
        logger.info("Starting XLSX metadata persistence for document: %s", context.document_id)

        try:
            await self._save_xlsx_metadata(context, xlsx_metadata)
        except Exception as e:
            logger.exception("Failed to save XLSX metadata for document: %s", context.document_id)
            raise DatabaseError(message=f"Failed to save XLSX metadata: {e}") from e

        persistence_duration = time.time() - persistence_start
        context.stage_timings["persistence"] = persistence_duration
        logger.info(
            "XLSX metadata persistence completed for document: %s (duration: %.3fs)",
            context.document_id,
            persistence_duration,
        )

        # Stage 3: Update Document Status to Ready (no chunks created for XLSX)
        try:
            await self._update_document_status_to_ready(context.document_id, context.user_id)
        except Exception as e:
            logger.exception("Failed to update document status for document: %s", context.document_id)
            raise DatabaseError(message=f"Failed to update document status: {e}") from e

        logger.info(
            "XLSX processing completed successfully: %s (sheets: %d, total stages: %d)",
            context.document_id,
            xlsx_metadata.total_sheets,
            len(context.stage_timings),
        )

    async def _save_xlsx_metadata(
        self,
        context: ProcessingContext,
        xlsx_metadata: Any,  # XLSXMetadata in runtime
    ) -> None:
        """Save XLSX metadata structure to document.meta['xlsx_structure'].

        Args:
            context: ProcessingContext with document info
            xlsx_metadata: XLSXMetadata object with sheet/column information

        Raises:
            Exception: If database update fails
        """
        from sqlalchemy import update

        # Build xlsx_structure for document.meta
        xlsx_structure = {
            "sheet_names": xlsx_metadata.sheet_names,
            "total_sheets": xlsx_metadata.total_sheets,
            "sheets": xlsx_metadata.sheets,
        }

        # Update document meta with xlsx_structure
        stmt = (
            update(Document)
            .where(
                Document.id == context.document_id,
                Document.user_id == context.user_id,
            )
            .values(
                meta={"xlsx_structure": xlsx_structure},
            )
        )

        result = await self._db.execute(stmt)
        await self._db.flush()

        # Verify the update happened
        if result.rowcount == 0:
            raise Exception(f"Document not found or metadata not updated: {context.document_id}")

        logger.debug(
            "Saved XLSX metadata to document %s: %d sheets",
            context.document_id,
            xlsx_metadata.total_sheets,
        )

    async def _upsert_chunks(
        self,
        context: ProcessingContext,
        chunks: list[Any],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert chunks to database with ON CONFLICT DO UPDATE.

        Args:
            context: ProcessingContext with document info
            chunks: List of LegalChunk objects
            embeddings: List of embedding vectors matching chunks

        Raises:
            Exception: If database operation fails
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # Prepare chunk data for upsert
        chunk_values = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_values.append({
                "document_id": context.document_id,
                "user_id": context.user_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding": embedding,
                "section_hint": chunk.section_hint,
                "section_path": chunk.section_path,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "anchors": chunk.anchors,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
            })

        if not chunk_values:
            logger.warning("No chunks to upsert for document: %s", context.document_id)
            return

        # Build upsert statement
        stmt = pg_insert(Chunk).values(chunk_values)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["document_id", "chunk_index"],
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "section_hint": stmt.excluded.section_hint,
                "section_path": stmt.excluded.section_path,
                "page_start": stmt.excluded.page_start,
                "page_end": stmt.excluded.page_end,
                "anchors": stmt.excluded.anchors,
                "char_start": stmt.excluded.char_start,
                "char_end": stmt.excluded.char_end,
            },
        )

        await self._db.execute(upsert_stmt)
        await self._db.flush()

        logger.debug(
            "Upserted %d chunks for document: %s",
            len(chunk_values),
            context.document_id,
        )

    async def _update_document_status_to_ready(
        self,
        document_id: str,
        user_id: str,
    ) -> None:
        """Update document status to 'ready' and set processed_at timestamp.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS

        Raises:
            Exception: If database update fails
        """
        from datetime import UTC, datetime

        from sqlalchemy import update

        stmt = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
            .values(
                status="ready",
                processed_at=datetime.now(UTC),
                error_msg=None,  # Clear any previous error
            )
        )

        result = await self._db.execute(stmt)
        await self._db.flush()

        # Verify the update happened
        if result.rowcount == 0:
            raise Exception(f"Document not found or not updated: {document_id}")

        logger.debug(
            "Updated document %s status to 'ready'",
            document_id,
        )

    async def _update_document_status_to_failed(
        self,
        document_id: str,
        user_id: str,
        error_msg: str,
    ) -> None:
        """Update document status to 'failed' with error message.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            error_msg: Error message to store

        Raises:
            Exception: If database update fails
        """
        from sqlalchemy import update

        stmt = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
            .values(
                status="failed",
                error_msg=error_msg,
            )
        )

        await self._db.execute(stmt)
        await self._db.flush()

        logger.debug(
            "Updated document %s status to 'failed': %s",
            document_id,
            error_msg[:100],  # Log first 100 chars
        )

    def _cleanup_temp_file(self, file_path: Path) -> None:
        """Clean up temporary file after processing.

        Args:
            file_path: Path to the temporary file to delete

        Notes:
            - Logs warning if file doesn't exist (already cleaned)
            - Logs error if cleanup fails but doesn't raise
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug("Cleaned up temp file: %s", file_path)
            else:
                logger.warning("Temp file already cleaned: %s", file_path)
        except PermissionError as e:
            logger.error("Permission error cleaning up temp file %s: %s", file_path, e)
        except OSError as e:
            logger.error("OS error cleaning up temp file %s: %s", file_path, e)


__all__ = [
    "DocumentProcessor",
    "ProcessingContext",
]
