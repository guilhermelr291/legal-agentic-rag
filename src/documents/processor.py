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
from src.documents.models import Document
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

            # TODO: T4, T5 - Route to appropriate processor based on file type
            # For now, just log that we have the file ready
            logger.info(
                "Document %s downloaded to %s, ready for processing",
                document_id,
                tmp_path,
            )

        except Exception:
            # Log and re-raise for outer error handling
            logger.exception("Error during document processing: %s", document_id)
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
        """
        # TODO: Implement in T4
        raise NotImplementedError("_process_pdf_docx() to be implemented in T4")

    async def _process_xlsx(self, context: ProcessingContext) -> None:
        """Process XLSX file: extract metadata → persist.

        Args:
            context: ProcessingContext with document information

        Raises:
            ExtractionFailedError: If metadata extraction fails
            DatabaseError: If database persistence fails
        """
        # TODO: Implement in T5
        raise NotImplementedError("_process_xlsx() to be implemented in T5")

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
