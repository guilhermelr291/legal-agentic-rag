"""Document processing exception hierarchy.

Provides specific exceptions for each stage of the document processing pipeline,
with error codes for programmatic handling and stage information for observability.

All exceptions inherit from DocumentProcessingError, which extends the global
ProcessingError from src.common.exceptions.
"""

from src.common.exceptions import ProcessingError


class DocumentProcessingError(ProcessingError):
    """Base for document processing pipeline errors.

    Attributes:
        message: Human-readable error description
        stage: Which pipeline stage failed ('extraction', 'chunking', 'embedding', 'persistence')
        code: Machine-readable error code for programmatic handling
    """

    def __init__(self, message: str, stage: str, code: str) -> None:
        super().__init__(message, code)
        self.stage = stage


class ExtractionFailedError(DocumentProcessingError):
    """Text extraction failed (PDF/DOCX).

    Attributes:
        message: Human-readable error description
        stage: Always 'extraction'
        code: Always 'EXTRACTION_FAILED'
        file_type: The file type that failed extraction (e.g., 'pdf', 'docx', 'xlsx')
    """

    def __init__(self, message: str, file_type: str) -> None:
        super().__init__(
            message=f"Failed to extract text from {file_type}: {message}",
            stage="extraction",
            code="EXTRACTION_FAILED",
        )
        self.file_type = file_type


class NoTextContentError(DocumentProcessingError):
    """Document has no extractable text.

    Attributes:
        message: Always "Document contains no extractable text"
        stage: Always 'extraction'
        code: Always 'NO_TEXT_CONTENT'
    """

    def __init__(self) -> None:
        super().__init__(
            message="Document contains no extractable text",
            stage="extraction",
            code="NO_TEXT_CONTENT",
        )


class ChunkingFailedError(DocumentProcessingError):
    """Legal chunking failed.

    Attributes:
        message: Human-readable error description including failure details
        stage: Always 'chunking'
        code: Always 'CHUNKING_FAILED'
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message=f"Failed to chunk document: {message}",
            stage="chunking",
            code="CHUNKING_FAILED",
        )


class EmbeddingGenerationError(DocumentProcessingError):
    """Embedding API failed after retries.

    Attributes:
        message: Human-readable error description
        stage: Always 'embedding'
        code: Always 'EMBEDDING_FAILED'
        batch_number: The batch number that failed (None if not applicable)
    """

    def __init__(self, message: str, batch_number: int | None = None) -> None:
        super().__init__(
            message=f"Failed to generate embeddings: {message}",
            stage="embedding",
            code="EMBEDDING_FAILED",
        )
        self.batch_number = batch_number


class DatabaseError(DocumentProcessingError):
    """Database persistence failed.

    Attributes:
        message: Human-readable error description
        stage: Always 'persistence'
        code: Always 'DATABASE_ERROR'
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message=f"Database error: {message}",
            stage="persistence",
            code="DATABASE_ERROR",
        )
