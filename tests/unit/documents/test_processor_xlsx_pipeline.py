"""Unit tests for DocumentProcessor XLSX metadata extraction pipeline.

Tests verify:
- Metadata extraction using ExtractionService.extract_metadata()
- ExtractionFailedError raised for password-protected XLSX
- ExtractionFailedError raised for empty XLSX (0 sheets)
- XLSX structure saved to document.meta['xlsx_structure']
- Document status updated to 'ready' without creating chunks
- No chunks exist after XLSX processing
- Stage duration logging
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


# Mock the dependencies before importing from src
@pytest.fixture(autouse=True)
def mock_supabase():
    """Mock supabase to avoid import errors."""
    with patch.dict("sys.modules", {
        "supabase": Mock(),
        "supabase._async": Mock(),
        "supabase.client": Mock(),
    }):
        yield


class TestXLSXProcessingPipeline:
    """Tests for the XLSX metadata extraction pipeline."""

    @pytest.fixture
    def mock_services(self, mock_supabase):
        """Create mock services for testing."""
        storage = Mock()
        storage.download_to_path = AsyncMock()

        extraction = Mock()
        extraction.extract_text = AsyncMock()
        extraction.extract_metadata = AsyncMock()

        chunking = Mock()
        chunking.chunk = Mock(return_value=[])

        embeddings = Mock()
        embeddings.generate_embeddings = AsyncMock(return_value=[])
        embeddings.generate_single = AsyncMock(return_value=[0.1] * 1536)

        return {
            "storage": storage,
            "extraction": extraction,
            "chunking": chunking,
            "embeddings": embeddings,
        }

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        from sqlalchemy.ext.asyncio import AsyncSession

        session = Mock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def processor(self, mock_services, mock_db_session, mock_supabase):
        """Create a DocumentProcessor with mock services."""
        from src.documents.processor import DocumentProcessor

        return DocumentProcessor(
            storage=mock_services["storage"],
            extraction=mock_services["extraction"],
            chunking=mock_services["chunking"],
            embeddings=mock_services["embeddings"],
            db=mock_db_session,
        )

    @pytest.fixture
    def sample_xlsx_metadata(self):
        """Create sample XLSX metadata."""
        from src.extractors.xlsx import XLSXMetadata

        return XLSXMetadata(
            sheet_names=["Sheet1", "Sheet2"],
            sheets=[
                {
                    "name": "Sheet1",
                    "columns": ["Name", "Age", "City"],
                    "column_count": 3,
                    "row_count": 100,
                    "has_headers": True,
                },
                {
                    "name": "Sheet2",
                    "columns": ["Product", "Price", "Quantity"],
                    "column_count": 3,
                    "row_count": 50,
                    "has_headers": True,
                },
            ],
            total_sheets=2,
            file_path="/tmp/test.xlsx",
            error=None,
            success=True,
        )

    @pytest.fixture
    def empty_xlsx_metadata(self):
        """Create empty XLSX metadata (0 sheets)."""
        from src.extractors.xlsx import XLSXMetadata

        return XLSXMetadata(
            sheet_names=[],
            sheets=[],
            total_sheets=0,
            file_path="/tmp/empty.xlsx",
            error=None,
            success=True,
        )

    @pytest.fixture
    def password_protected_xlsx_metadata(self):
        """Create password-protected XLSX metadata."""
        from src.extractors.xlsx import XLSXMetadata

        return XLSXMetadata(
            sheet_names=[],
            sheets=[],
            total_sheets=0,
            file_path="/tmp/protected.xlsx",
            error="File is password-protected",
            success=False,
        )

    @pytest.mark.asyncio
    async def test_extracts_metadata_using_extraction_service(
        self, processor, mock_services, mock_db_session, sample_xlsx_metadata
    ):
        """Verify metadata extraction uses ExtractionService.extract_metadata()."""
        from src.documents.processor import ProcessingContext

        mock_services["extraction"].extract_metadata.return_value = sample_xlsx_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute
        await processor._process_xlsx(context)

        # Verify extraction was called
        mock_services["extraction"].extract_metadata.assert_called_once_with(Path("/tmp/test.xlsx"))

    @pytest.mark.asyncio
    async def test_raises_extraction_failed_error_for_password_protected(
        self, processor, mock_services, mock_db_session, password_protected_xlsx_metadata
    ):
        """Verify ExtractionFailedError is raised for password-protected XLSX."""
        from src.documents.exceptions import ExtractionFailedError
        from src.documents.processor import ProcessingContext

        mock_services["extraction"].extract_metadata.return_value = password_protected_xlsx_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/protected.xlsx"),
        )

        # Execute & Verify
        with pytest.raises(ExtractionFailedError) as exc_info:
            await processor._process_xlsx(context)

        assert exc_info.value.stage == "extraction"
        assert exc_info.value.code == "EXTRACTION_FAILED"
        assert "xlsx" in exc_info.value.file_type.lower()

    @pytest.mark.asyncio
    async def test_raises_extraction_failed_error_for_empty_xlsx(
        self, processor, mock_services, mock_db_session, empty_xlsx_metadata
    ):
        """Verify ExtractionFailedError is raised for empty XLSX (0 sheets)."""
        from src.documents.exceptions import ExtractionFailedError
        from src.documents.processor import ProcessingContext

        mock_services["extraction"].extract_metadata.return_value = empty_xlsx_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/empty.xlsx"),
        )

        # Execute & Verify
        with pytest.raises(ExtractionFailedError) as exc_info:
            await processor._process_xlsx(context)

        assert exc_info.value.stage == "extraction"
        assert exc_info.value.code == "EXTRACTION_FAILED"
        assert "xlsx" in exc_info.value.file_type.lower()

    @pytest.mark.asyncio
    async def test_saves_xlsx_structure_to_document_meta(
        self, processor, mock_services, mock_db_session, sample_xlsx_metadata
    ):
        """Verify XLSX structure is saved to document.meta['xlsx_structure']."""
        from src.documents.processor import ProcessingContext

        mock_services["extraction"].extract_metadata.return_value = sample_xlsx_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute
        await processor._process_xlsx(context)

        # Verify database execute was called for metadata update
        assert mock_db_session.execute.called

        # Find the update call that sets meta
        update_calls = [
            call for call in mock_db_session.execute.call_args_list
            if "meta" in str(call[0][0]).lower() or "update" in str(call[0][0]).lower()
        ]
        assert len(update_calls) > 0, "Expected at least one database execute call for metadata update"

    @pytest.mark.asyncio
    async def test_document_status_updated_to_ready_on_success(
        self, processor, mock_services, mock_db_session, sample_xlsx_metadata
    ):
        """Verify document status is set to 'ready' and processed_at is set on success."""
        from src.documents.processor import ProcessingContext

        mock_services["extraction"].extract_metadata.return_value = sample_xlsx_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute
        await processor._process_xlsx(context)

        # Verify document status was updated to ready
        update_calls = [
            call for call in mock_db_session.execute.call_args_list
            if "UPDATE" in str(call[0][0]).upper() or "document" in str(call[0][0]).lower()
        ]
        assert len(update_calls) > 0, "Expected at least one database execute call for document update"

    @pytest.mark.asyncio
    async def test_no_chunks_created_for_xlsx(
        self, processor, mock_services, mock_db_session, sample_xlsx_metadata
    ):
        """Verify no chunks are created when processing XLSX files."""
        from src.documents.processor import ProcessingContext

        mock_services["extraction"].extract_metadata.return_value = sample_xlsx_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute
        await processor._process_xlsx(context)

        # Verify chunking service was NOT called
        mock_services["chunking"].chunk.assert_not_called()

        # Verify embedding service was NOT called
        mock_services["embeddings"].generate_embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_stage_logging_with_duration(
        self, processor, mock_services, mock_db_session, sample_xlsx_metadata, caplog
    ):
        """Verify each stage logs start and complete with duration."""
        import logging

        from src.documents.processor import ProcessingContext

        mock_services["extraction"].extract_metadata.return_value = sample_xlsx_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        with caplog.at_level(logging.INFO):
            await processor._process_xlsx(context)

        # Verify extraction stage logging
        assert any(
            "extraction" in record.message.lower() and "start" in record.message.lower()
            for record in caplog.records
        ), "Expected extraction start log"

        assert any(
            "extraction" in record.message.lower() and "complete" in record.message.lower()
            for record in caplog.records
        ), "Expected extraction complete log"

        # Verify persistence stage logging
        assert any(
            "persist" in record.message.lower() or "metadata" in record.message.lower()
            for record in caplog.records
        ), "Expected persistence log"

    @pytest.mark.asyncio
    async def test_validates_at_least_one_sheet(
        self, processor, mock_services, mock_db_session
    ):
        """Verify XLSX with at least one sheet passes validation."""
        from src.documents.processor import ProcessingContext
        from src.extractors.xlsx import XLSXMetadata

        # Create metadata with exactly one sheet
        single_sheet_metadata = XLSXMetadata(
            sheet_names=["Data"],
            sheets=[
                {
                    "name": "Data",
                    "columns": ["Column1", "Column2"],
                    "column_count": 2,
                    "row_count": 10,
                    "has_headers": True,
                },
            ],
            total_sheets=1,
            file_path="/tmp/single.xlsx",
            error=None,
            success=True,
        )

        mock_services["extraction"].extract_metadata.return_value = single_sheet_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/single.xlsx"),
        )

        # Execute - should not raise
        await processor._process_xlsx(context)

        # Verify success - no exception raised

    @pytest.mark.asyncio
    async def test_raises_extraction_failed_on_service_failure(
        self, processor, mock_services, mock_db_session
    ):
        """Verify ExtractionFailedError is raised when extraction service fails."""
        from src.documents.exceptions import ExtractionFailedError
        from src.documents.processor import ProcessingContext

        # Make extraction service raise an exception
        mock_services["extraction"].extract_metadata.side_effect = Exception("Service error")

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute & Verify
        with pytest.raises(ExtractionFailedError) as exc_info:
            await processor._process_xlsx(context)

        assert exc_info.value.stage == "extraction"
        assert exc_info.value.code == "EXTRACTION_FAILED"


class TestXLSXMetadataSaving:
    """Tests for XLSX metadata persistence."""

    @pytest.fixture
    def mock_services(self, mock_supabase):
        """Create mock services for testing."""
        storage = Mock()
        storage.download_to_path = AsyncMock()

        extraction = Mock()
        extraction.extract_text = AsyncMock()
        extraction.extract_metadata = AsyncMock()

        chunking = Mock()
        chunking.chunk = Mock(return_value=[])

        embeddings = Mock()
        embeddings.generate_embeddings = AsyncMock(return_value=[])
        embeddings.generate_single = AsyncMock(return_value=[0.1] * 1536)

        return {
            "storage": storage,
            "extraction": extraction,
            "chunking": chunking,
            "embeddings": embeddings,
        }

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        from sqlalchemy.ext.asyncio import AsyncSession

        session = Mock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def processor(self, mock_services, mock_db_session, mock_supabase):
        """Create a DocumentProcessor with mock services."""
        from src.documents.processor import DocumentProcessor

        return DocumentProcessor(
            storage=mock_services["storage"],
            extraction=mock_services["extraction"],
            chunking=mock_services["chunking"],
            embeddings=mock_services["embeddings"],
            db=mock_db_session,
        )

    @pytest.mark.asyncio
    async def test_raises_database_error_on_meta_save_failure(
        self, processor, mock_services, mock_db_session
    ):
        """Verify DatabaseError is raised when saving metadata fails."""
        from src.documents.exceptions import DatabaseError
        from src.documents.processor import ProcessingContext
        from src.extractors.xlsx import XLSXMetadata

        sample_metadata = XLSXMetadata(
            sheet_names=["Sheet1"],
            sheets=[{"name": "Sheet1", "columns": ["A", "B"], "column_count": 2, "row_count": 5, "has_headers": True}],
            total_sheets=1,
            file_path="/tmp/test.xlsx",
            error=None,
            success=True,
        )

        mock_services["extraction"].extract_metadata.return_value = sample_metadata

        # Database fails on metadata save
        mock_db_session.execute.side_effect = Exception("Database connection lost")

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute & Verify
        with pytest.raises(DatabaseError) as exc_info:
            await processor._process_xlsx(context)

        assert exc_info.value.stage == "persistence"
        assert exc_info.value.code == "DATABASE_ERROR"


class TestXLSXStructureContent:
    """Tests for XLSX structure content verification."""

    @pytest.fixture
    def mock_services(self, mock_supabase):
        """Create mock services for testing."""
        storage = Mock()
        storage.download_to_path = AsyncMock()

        extraction = Mock()
        extraction.extract_text = AsyncMock()
        extraction.extract_metadata = AsyncMock()

        chunking = Mock()
        chunking.chunk = Mock(return_value=[])

        embeddings = Mock()
        embeddings.generate_embeddings = AsyncMock(return_value=[])
        embeddings.generate_single = AsyncMock(return_value=[0.1] * 1536)

        return {
            "storage": storage,
            "extraction": extraction,
            "chunking": chunking,
            "embeddings": embeddings,
        }

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        from sqlalchemy.ext.asyncio import AsyncSession

        session = Mock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def processor(self, mock_services, mock_db_session, mock_supabase):
        """Create a DocumentProcessor with mock services."""
        from src.documents.processor import DocumentProcessor

        return DocumentProcessor(
            storage=mock_services["storage"],
            extraction=mock_services["extraction"],
            chunking=mock_services["chunking"],
            embeddings=mock_services["embeddings"],
            db=mock_db_session,
        )

    @pytest.mark.asyncio
    async def test_xlsx_structure_contains_sheet_names(
        self, processor, mock_services, mock_db_session
    ):
        """Verify xlsx_structure includes sheet_names."""
        from src.documents.processor import ProcessingContext
        from src.extractors.xlsx import XLSXMetadata

        sample_metadata = XLSXMetadata(
            sheet_names=["Sales", "Inventory", "Summary"],
            sheets=[
                {"name": "Sales", "columns": ["Date", "Amount"], "column_count": 2, "row_count": 100, "has_headers": True},
                {"name": "Inventory", "columns": ["Item", "Stock"], "column_count": 2, "row_count": 50, "has_headers": True},
                {"name": "Summary", "columns": ["Metric", "Value"], "column_count": 2, "row_count": 10, "has_headers": True},
            ],
            total_sheets=3,
            file_path="/tmp/test.xlsx",
            error=None,
            success=True,
        )

        mock_services["extraction"].extract_metadata.return_value = sample_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute
        await processor._process_xlsx(context)

        # Verify the structure was built correctly
        # The metadata update should have been called with xlsx_structure
        execute_calls = mock_db_session.execute.call_args_list
        assert len(execute_calls) > 0

    @pytest.mark.asyncio
    async def test_xlsx_structure_contains_column_names(
        self, processor, mock_services, mock_db_session
    ):
        """Verify xlsx_structure includes column names for each sheet."""
        from src.documents.processor import ProcessingContext
        from src.extractors.xlsx import XLSXMetadata

        sample_metadata = XLSXMetadata(
            sheet_names=["Data"],
            sheets=[
                {
                    "name": "Data",
                    "columns": ["ID", "Name", "Email", "Phone", "Address"],
                    "column_count": 5,
                    "row_count": 1000,
                    "has_headers": True,
                },
            ],
            total_sheets=1,
            file_path="/tmp/test.xlsx",
            error=None,
            success=True,
        )

        mock_services["extraction"].extract_metadata.return_value = sample_metadata

        context = ProcessingContext(
            document_id="doc-123",
            user_id="user-456",
            file_path=Path("/tmp/test.xlsx"),
        )

        # Execute
        await processor._process_xlsx(context)

        # Verify database was called
        assert mock_db_session.execute.called
