"""Unit tests for document processing exception hierarchy.

Tests verify:
- Exception classes can be instantiated with correct attributes
- Exception hierarchy is correct (all inherit from DocumentProcessingError)
- Error codes match spec requirements
"""

import pytest

from src.documents.exceptions import (
    DatabaseError,
    DocumentProcessingError,
    EmbeddingGenerationError,
    ExtractionFailedError,
    NoTextContentError,
    ChunkingFailedError,
)
from src.common.exceptions import ProcessingError


class TestDocumentProcessingError:
    """Tests for the base DocumentProcessingError class."""

    def test_inherits_from_processing_error(self):
        """Verify DocumentProcessingError inherits from ProcessingError."""
        exc = DocumentProcessingError("test message", "test_stage", "TEST_CODE")
        assert isinstance(exc, ProcessingError)

    def test_has_message_attribute(self):
        """Verify exception has message attribute."""
        exc = DocumentProcessingError("test message", "test_stage", "TEST_CODE")
        assert exc.message == "test message"

    def test_has_stage_attribute(self):
        """Verify exception has stage attribute."""
        exc = DocumentProcessingError("test message", "extraction", "TEST_CODE")
        assert exc.stage == "extraction"

    def test_has_code_attribute(self):
        """Verify exception has code attribute."""
        exc = DocumentProcessingError("test message", "test_stage", "TEST_CODE")
        assert exc.code == "TEST_CODE"

    def test_str_includes_code_and_message(self):
        """Verify string representation includes code and message."""
        exc = DocumentProcessingError("test message", "test_stage", "TEST_CODE")
        assert str(exc) == "[TEST_CODE] test message"


class TestExtractionFailedError:
    """Tests for ExtractionFailedError."""

    def test_inherits_from_document_processing_error(self):
        """Verify ExtractionFailedError inherits from DocumentProcessingError."""
        exc = ExtractionFailedError("error details", "pdf")
        assert isinstance(exc, DocumentProcessingError)

    def test_has_file_type_attribute(self):
        """Verify exception has file_type attribute."""
        exc = ExtractionFailedError("error details", "docx")
        assert exc.file_type == "docx"

    def test_sets_correct_stage(self):
        """Verify stage is set to 'extraction'."""
        exc = ExtractionFailedError("error details", "pdf")
        assert exc.stage == "extraction"

    def test_sets_correct_code(self):
        """Verify code is set to 'EXTRACTION_FAILED'."""
        exc = ExtractionFailedError("error details", "pdf")
        assert exc.code == "EXTRACTION_FAILED"

    def test_message_includes_file_type(self):
        """Verify message includes file type."""
        exc = ExtractionFailedError("corrupted file", "pdf")
        assert "pdf" in exc.message
        assert "corrupted file" in exc.message


class TestNoTextContentError:
    """Tests for NoTextContentError."""

    def test_inherits_from_document_processing_error(self):
        """Verify NoTextContentError inherits from DocumentProcessingError."""
        exc = NoTextContentError()
        assert isinstance(exc, DocumentProcessingError)

    def test_sets_correct_stage(self):
        """Verify stage is set to 'extraction'."""
        exc = NoTextContentError()
        assert exc.stage == "extraction"

    def test_sets_correct_code(self):
        """Verify code is set to 'NO_TEXT_CONTENT'."""
        exc = NoTextContentError()
        assert exc.code == "NO_TEXT_CONTENT"

    def test_has_descriptive_message(self):
        """Verify message indicates no extractable text."""
        exc = NoTextContentError()
        assert "no extractable text" in exc.message.lower()


class TestChunkingFailedError:
    """Tests for ChunkingFailedError."""

    def test_inherits_from_document_processing_error(self):
        """Verify ChunkingFailedError inherits from DocumentProcessingError."""
        exc = ChunkingFailedError("chunking error")
        assert isinstance(exc, DocumentProcessingError)

    def test_sets_correct_stage(self):
        """Verify stage is set to 'chunking'."""
        exc = ChunkingFailedError("chunking error")
        assert exc.stage == "chunking"

    def test_sets_correct_code(self):
        """Verify code is set to 'CHUNKING_FAILED'."""
        exc = ChunkingFailedError("chunking error")
        assert exc.code == "CHUNKING_FAILED"

    def test_message_includes_error_details(self):
        """Verify message includes the error details."""
        exc = ChunkingFailedError("tokenizer failed")
        assert "tokenizer failed" in exc.message


class TestEmbeddingGenerationError:
    """Tests for EmbeddingGenerationError."""

    def test_inherits_from_document_processing_error(self):
        """Verify EmbeddingGenerationError inherits from DocumentProcessingError."""
        exc = EmbeddingGenerationError("api error")
        assert isinstance(exc, DocumentProcessingError)

    def test_has_batch_number_attribute(self):
        """Verify exception has batch_number attribute."""
        exc = EmbeddingGenerationError("api error", batch_number=5)
        assert exc.batch_number == 5

    def test_batch_number_can_be_none(self):
        """Verify batch_number can be None."""
        exc = EmbeddingGenerationError("api error")
        assert exc.batch_number is None

    def test_sets_correct_stage(self):
        """Verify stage is set to 'embedding'."""
        exc = EmbeddingGenerationError("api error")
        assert exc.stage == "embedding"

    def test_sets_correct_code(self):
        """Verify code is set to 'EMBEDDING_FAILED'."""
        exc = EmbeddingGenerationError("api error")
        assert exc.code == "EMBEDDING_FAILED"

    def test_message_includes_error_details(self):
        """Verify message includes the error details."""
        exc = EmbeddingGenerationError("rate limit exceeded")
        assert "rate limit exceeded" in exc.message


class TestDatabaseError:
    """Tests for DatabaseError."""

    def test_inherits_from_document_processing_error(self):
        """Verify DatabaseError inherits from DocumentProcessingError."""
        exc = DatabaseError("connection failed")
        assert isinstance(exc, DocumentProcessingError)

    def test_sets_correct_stage(self):
        """Verify stage is set to 'persistence'."""
        exc = DatabaseError("connection failed")
        assert exc.stage == "persistence"

    def test_sets_correct_code(self):
        """Verify code is set to 'DATABASE_ERROR'."""
        exc = DatabaseError("connection failed")
        assert exc.code == "DATABASE_ERROR"

    def test_message_includes_error_details(self):
        """Verify message includes the error details."""
        exc = DatabaseError("timeout")
        assert "timeout" in exc.message


class TestExceptionHierarchy:
    """Tests to verify the complete exception hierarchy."""

    @pytest.mark.parametrize(
        "exc_class,kwargs",
        [
            (ExtractionFailedError, {"message": "error", "file_type": "pdf"}),
            (NoTextContentError, {}),
            (ChunkingFailedError, {"message": "error"}),
            (EmbeddingGenerationError, {"message": "error"}),
            (DatabaseError, {"message": "error"}),
        ],
    )
    def test_all_exceptions_inherit_from_document_processing_error(
        self, exc_class, kwargs
    ):
        """Verify all specific exceptions inherit from DocumentProcessingError."""
        exc = exc_class(**kwargs)
        assert isinstance(exc, DocumentProcessingError)
        assert exc.__class__.__bases__[0] == DocumentProcessingError

    def test_all_exceptions_have_required_attributes(self):
        """Verify all exceptions have message, stage, and code attributes."""
        exceptions = [
            ExtractionFailedError("error", "pdf"),
            NoTextContentError(),
            ChunkingFailedError("error"),
            EmbeddingGenerationError("error", batch_number=1),
            DatabaseError("error"),
        ]

        for exc in exceptions:
            assert hasattr(exc, "message")
            assert hasattr(exc, "stage")
            assert hasattr(exc, "code")
            assert exc.message is not None
            assert exc.stage is not None
            assert exc.code is not None
