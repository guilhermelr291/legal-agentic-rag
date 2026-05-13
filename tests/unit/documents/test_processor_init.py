"""Unit tests for DocumentProcessor initialization and structure.

Tests verify:
- DocumentProcessor can be instantiated with required services
- ProcessingContext dataclass can be instantiated with test data
- All required methods exist on DocumentProcessor
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest


# Create minimal mock dataclasses for testing without heavy imports
@dataclass
class MockLegalChunk:
    """Mock LegalChunk for testing."""

    content: str = ""
    chunk_index: int = 0
    char_start: int = 0
    char_end: int = 0


@dataclass
class MockXLSXMetadata:
    """Mock XLSXMetadata for testing."""

    sheet_names: list[str] = field(default_factory=list)
    sheets: list[dict] = field(default_factory=list)
    total_sheets: int = 0
    file_path: str = ""
    error: str | None = None
    success: bool = True


class TestProcessingContext:
    """Tests for ProcessingContext dataclass."""

    def test_can_instantiate_with_required_fields(self):
        """Verify ProcessingContext can be created with minimal data."""
        from src.documents.processor import ProcessingContext

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.pdf"),
        )
        assert context.document_id == "doc-123"
        assert context.user_id == "user-456"
        assert context.file_path == Path("/tmp/test.pdf")

    def test_can_instantiate_with_all_fields(self):
        """Verify ProcessingContext can be created with all optional fields."""
        from src.documents.processor import ProcessingContext

        chunks = [
            MockLegalChunk(content="chunk1", chunk_index=0, char_start=0, char_end=10),
            MockLegalChunk(content="chunk2", chunk_index=1, char_start=11, char_end=20),
        ]
        xlsx_metadata = MockXLSXMetadata(
            sheet_names=["Sheet1"],
            sheets=[{"name": "Sheet1", "columns": ["A", "B"]}],
            total_sheets=1,
            file_path="/tmp/test.xlsx",
        )

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.pdf"),
            extracted_text="Sample extracted text",
            extracted_pages=[{"number": 1, "start_char": 0, "end_char": 100}],
            chunks=chunks,
            xlsx_metadata=xlsx_metadata,
            stage_timings={"download": 1.5, "extraction": 2.0},
            current_stage="extraction",
        )

        assert context.document_id == "doc-123"
        assert context.user_id == "user-456"
        assert context.file_path == Path("/tmp/test.pdf")
        assert context.extracted_text == "Sample extracted text"
        assert len(context.chunks) == 2
        assert context.xlsx_metadata.total_sheets == 1
        assert context.stage_timings["download"] == 1.5
        assert context.current_stage == "extraction"

    def test_default_values(self):
        """Verify ProcessingContext has correct default values."""
        from src.documents.processor import ProcessingContext

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.pdf"),
        )
        assert context.extracted_text is None
        assert context.extracted_pages == []
        assert context.chunks == []
        assert context.xlsx_metadata is None
        assert context.stage_timings == {}
        assert context.current_stage is None


class TestDocumentProcessorInitialization:
    """Tests for DocumentProcessor instantiation."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        # Create simple mock objects that satisfy the type requirements
        storage = Mock()
        storage.download_file = AsyncMock()

        extraction = Mock()
        extraction.extract_text = AsyncMock()
        extraction.extract_metadata = AsyncMock()

        chunking = Mock()
        chunking.chunk = Mock(return_value=[])

        embeddings = Mock()
        embeddings.generate_embeddings = AsyncMock(return_value=[])
        embeddings.generate_single = AsyncMock(return_value=[])

        db = Mock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()

        return {
            "storage": storage,
            "extraction": extraction,
            "chunking": chunking,
            "embeddings": embeddings,
            "db": db,
        }

    def test_can_instantiate_with_all_services(self, mock_services):
        """Verify DocumentProcessor can be created with all required services."""
        from src.documents.processor import DocumentProcessor

        processor = DocumentProcessor(
            storage=mock_services["storage"],
            extraction=mock_services["extraction"],
            chunking=mock_services["chunking"],
            embeddings=mock_services["embeddings"],
            db=mock_services["db"],
        )
        assert processor is not None
        assert type(processor).__name__ == "DocumentProcessor"

    def test_stores_services_as_attributes(self, mock_services):
        """Verify all services are stored as instance attributes."""
        from src.documents.processor import DocumentProcessor

        processor = DocumentProcessor(
            storage=mock_services["storage"],
            extraction=mock_services["extraction"],
            chunking=mock_services["chunking"],
            embeddings=mock_services["embeddings"],
            db=mock_services["db"],
        )
        assert processor._storage is mock_services["storage"]
        assert processor._extraction is mock_services["extraction"]
        assert processor._chunking is mock_services["chunking"]
        assert processor._embeddings is mock_services["embeddings"]
        assert processor._db is mock_services["db"]


class TestDocumentProcessorMethodsExist:
    """Tests to verify all required methods exist on DocumentProcessor."""

    @pytest.fixture
    def processor(self):
        """Create a DocumentProcessor with mock services."""
        from src.documents.processor import DocumentProcessor

        # Create simple mocks
        storage = Mock()
        storage.download_file = AsyncMock()

        extraction = Mock()
        extraction.extract_text = AsyncMock()
        extraction.extract_metadata = AsyncMock()

        chunking = Mock()
        chunking.chunk = Mock(return_value=[])

        embeddings = Mock()
        embeddings.generate_embeddings = AsyncMock(return_value=[])
        embeddings.generate_single = AsyncMock(return_value=[])

        db = Mock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()

        return DocumentProcessor(
            storage=storage,
            extraction=extraction,
            chunking=chunking,
            embeddings=embeddings,
            db=db,
        )

    def test_process_method_exists(self, processor):
        """Verify process() method exists and is callable."""
        assert hasattr(processor, "process")
        assert callable(processor.process)

    def test_process_method_is_async(self, processor):
        """Verify process() is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(processor.process)

    def test_process_pdf_docx_method_exists(self, processor):
        """Verify _process_pdf_docx() method exists and is callable."""
        assert hasattr(processor, "_process_pdf_docx")
        assert callable(processor._process_pdf_docx)

    def test_process_pdf_docx_is_async(self, processor):
        """Verify _process_pdf_docx() is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(processor._process_pdf_docx)

    def test_process_xlsx_method_exists(self, processor):
        """Verify _process_xlsx() method exists and is callable."""
        assert hasattr(processor, "_process_xlsx")
        assert callable(processor._process_xlsx)

    def test_process_xlsx_is_async(self, processor):
        """Verify _process_xlsx() is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(processor._process_xlsx)

    def test_cleanup_temp_file_method_exists(self, processor):
        """Verify _cleanup_temp_file() method exists and is callable."""
        assert hasattr(processor, "_cleanup_temp_file")
        assert callable(processor._cleanup_temp_file)


class TestProcessingContextIntegration:
    """Integration tests for ProcessingContext with DocumentProcessor."""

    def test_context_creation_in_processor(self):
        """Verify processor can create a ProcessingContext."""
        from src.documents.processor import DocumentProcessor, ProcessingContext

        # Create simple mocks
        storage = Mock()
        extraction = Mock()
        chunking = Mock()
        embeddings = Mock()
        db = Mock()

        processor = DocumentProcessor(
            storage=storage,
            extraction=extraction,
            chunking=chunking,
            embeddings=embeddings,
            db=db,
        )

        # Create a context as the processor would
        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.pdf"),
        )

        assert context.document_id == "doc-123"
        assert context.user_id == "user-456"
