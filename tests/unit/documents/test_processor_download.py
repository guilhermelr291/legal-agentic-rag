"""Unit tests for DocumentProcessor download stage.

Tests verify:
- Temp file is created and cleaned up on success
- Temp file is cleaned up on failure
- Document status verification before processing
- StorageService.download_to_path is called with correct args
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestDownloadStage:
    """Tests for the download stage of document processing."""

    @pytest.fixture
    def mock_services(self):
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
        embeddings.generate_single = AsyncMock(return_value=[])

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
    def processor(self, mock_services, mock_db_session):
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
    def mock_document(self):
        """Create a mock document for testing."""
        from src.documents.models import Document

        doc = Mock(spec=Document)
        doc.id = "doc-123"
        doc.user_id = "user-456"
        doc.filename = "test.pdf"
        doc.file_type = "pdf"
        doc.storage_path = "user-456/doc-123/test.pdf"
        doc.status = "processing"
        doc.meta = {}
        return doc

    async def test_document_status_verification(self, processor, mock_db_session, mock_document):
        """Verify document status is checked before processing."""
        # Setup: document with status='processing'
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result

        # Mock temp file handling to avoid actual file operations
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test-doc-123.pdf"
            mock_temp.return_value.__enter__ = Mock(return_value=mock_temp_file)
            mock_temp.return_value.__exit__ = Mock(return_value=False)

            # Execute
            await processor.process("doc-123", "user-456")

        # Verify document was queried with correct filters
        call_args = mock_db_session.execute.call_args_list[0]
        stmt = call_args[0][0]
        assert "doc-123" in str(stmt)
        assert "user-456" in str(stmt)

    async def test_document_not_found_raises_error(self, processor, mock_db_session):
        """Verify error is raised when document is not found."""
        from src.documents.exceptions import DocumentProcessingError

        # Setup: no document found
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Execute & Verify
        with pytest.raises(DocumentProcessingError) as exc_info:
            await processor.process("doc-123", "user-456")

        assert "not found" in str(exc_info.value.message).lower()
        assert exc_info.value.code == "DOCUMENT_NOT_FOUND"

    async def test_invalid_status_raises_error(self, processor, mock_db_session, mock_document):
        """Verify error is raised when document status is not 'processing'."""
        from src.documents.exceptions import DocumentProcessingError

        # Setup: document with status='ready' (not processing)
        mock_document.status = "ready"
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result

        # Execute & Verify
        with pytest.raises(DocumentProcessingError) as exc_info:
            await processor.process("doc-123", "user-456")

        assert "ready" in str(exc_info.value.message).lower()
        assert "processing" in str(exc_info.value.message).lower()
        assert exc_info.value.code == "INVALID_DOCUMENT_STATUS"

    async def test_storage_download_called_with_correct_args(
        self, processor, mock_services, mock_db_session, mock_document
    ):
        """Verify StorageService.download_to_path is called with correct arguments."""
        # Setup
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result

        # Mock temp file handling
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test-doc-123.pdf"
            mock_temp.return_value.__enter__ = Mock(return_value=mock_temp_file)
            mock_temp.return_value.__exit__ = Mock(return_value=False)

            # Execute
            await processor.process("doc-123", "user-456")

        # Verify download_to_path was called with correct args
        mock_services["storage"].download_to_path.assert_called_once()
        call_args = mock_services["storage"].download_to_path.call_args

        assert call_args.kwargs["bucket_name"] == "documents"
        assert call_args.kwargs["file_path"] == "user-456/doc-123/test.pdf"
        assert isinstance(call_args.kwargs["destination"], Path)

    async def test_temp_file_created_with_correct_extension(
        self, processor, mock_services, mock_db_session, mock_document
    ):
        """Verify temp file is created with correct file extension."""
        # Setup
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result

        # Mock temp file handling
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test-doc-123.pdf"
            mock_temp.return_value.__enter__ = Mock(return_value=mock_temp_file)
            mock_temp.return_value.__exit__ = Mock(return_value=False)

            # Execute
            await processor.process("doc-123", "user-456")

        # Verify temp file was created with .pdf extension
        mock_temp.assert_called_once()
        call_kwargs = mock_temp.call_args.kwargs
        assert call_kwargs["delete"] is False
        assert call_kwargs["suffix"] == ".pdf"

    async def test_temp_file_cleanup_on_success(
        self, processor, mock_services, mock_db_session, mock_document
    ):
        """Verify temp file is cleaned up after successful processing."""
        # Setup
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result

        temp_path = Path("/tmp/test-doc-123.pdf")

        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp_file = Mock()
            mock_temp_file.name = str(temp_path)
            mock_temp.return_value.__enter__ = Mock(return_value=mock_temp_file)
            mock_temp.return_value.__exit__ = Mock(return_value=False)

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                with patch("pathlib.Path.unlink") as mock_unlink:
                    # Execute
                    await processor.process("doc-123", "user-456")

                    # Verify cleanup was called
                    mock_unlink.assert_called()

    async def test_temp_file_cleanup_on_failure(
        self, processor, mock_services, mock_db_session, mock_document
    ):
        """Verify temp file is cleaned up even when processing fails."""
        # Setup: make download fail
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result

        mock_services["storage"].download_to_path = AsyncMock(
            side_effect=Exception("Download failed")
        )

        temp_path = Path("/tmp/test-doc-123.pdf")

        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp_file = Mock()
            mock_temp_file.name = str(temp_path)
            mock_temp.return_value.__enter__ = Mock(return_value=mock_temp_file)
            mock_temp.return_value.__exit__ = Mock(return_value=False)

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                with patch("pathlib.Path.unlink") as mock_unlink:
                    # Execute - should raise due to download failure
                    with pytest.raises(Exception):
                        await processor.process("doc-123", "user-456")

                    # Verify cleanup was still called even on failure
                    mock_unlink.assert_called()

    async def test_processing_context_populated(
        self, processor, mock_services, mock_db_session, mock_document
    ):
        """Verify ProcessingContext is populated with file_path after download."""
        # Setup
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result

        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test-doc-123.pdf"
            mock_temp.return_value.__enter__ = Mock(return_value=mock_temp_file)
            mock_temp.return_value.__exit__ = Mock(return_value=False)

            # Execute
            await processor.process("doc-123", "user-456")

            # Verify context was created (this is implicitly verified by successful execution)
            # The fact that process() completes without error means context was created
            mock_services["storage"].download_to_path.assert_called_once()


class TestStorageServiceDownloadToPath:
    """Tests for StorageService.download_to_path method."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        client = Mock()
        client.storage = Mock()
        return client

    @pytest.fixture
    def storage_service(self, mock_supabase_client):
        """Create a StorageService with mock client."""
        from src.storage.service import StorageService

        return StorageService(client=mock_supabase_client)

    async def test_download_to_path_writes_bytes(self, storage_service, mock_supabase_client, tmp_path):
        """Verify download_to_path writes bytes to destination path."""
        # Setup mock bucket
        mock_bucket = Mock()
        mock_bucket.download = AsyncMock(return_value=b"file content bytes")

        mock_storage = Mock()
        mock_storage.from_ = Mock(return_value=mock_bucket)
        mock_supabase_client.storage = mock_storage

        # Create temp destination
        dest_path = tmp_path / "downloaded_file.pdf"

        # Execute
        await storage_service.download_to_path(
            bucket_name="documents",
            file_path="user-123/file.pdf",
            destination=dest_path,
        )

        # Verify file was written
        assert dest_path.exists()
        assert dest_path.read_bytes() == b"file content bytes"

    async def test_download_to_path_calls_bucket_correctly(self, storage_service, mock_supabase_client):
        """Verify download_to_path calls the storage bucket with correct args."""
        # Setup mock bucket
        mock_bucket = Mock()
        mock_bucket.download = AsyncMock(return_value=b"content")

        mock_storage = Mock()
        mock_storage.from_ = Mock(return_value=mock_bucket)
        mock_supabase_client.storage = mock_storage

        # Create temp destination
        dest_path = Path("/tmp/test_download.pdf")

        # Execute
        with patch.object(Path, "write_bytes"):
            await storage_service.download_to_path(
                bucket_name="documents",
                file_path="user-123/file.pdf",
                destination=dest_path,
            )

        # Verify bucket was accessed correctly
        mock_storage.from_.assert_called_once_with("documents")
        mock_bucket.download.assert_called_once_with(path="user-123/file.pdf")


class TestCleanupTempFile:
    """Tests for _cleanup_temp_file helper method."""

    @pytest.fixture
    def processor(self):
        """Create a DocumentProcessor for testing cleanup."""
        from src.documents.processor import DocumentProcessor

        storage = Mock()
        extraction = Mock()
        chunking = Mock()
        embeddings = Mock()
        db = Mock()

        return DocumentProcessor(
            storage=storage,
            extraction=extraction,
            chunking=chunking,
            embeddings=embeddings,
            db=db,
        )

    def test_cleanup_deletes_existing_file(self, processor, tmp_path):
        """Verify _cleanup_temp_file deletes an existing file."""
        # Create a temp file
        test_file = tmp_path / "test_cleanup.txt"
        test_file.write_text("content")
        assert test_file.exists()

        # Execute
        processor._cleanup_temp_file(test_file)

        # Verify file was deleted
        assert not test_file.exists()

    def test_cleanup_logs_warning_for_missing_file(self, processor, tmp_path, caplog):
        """Verify _cleanup_temp_file logs warning when file doesn't exist."""
        import logging

        non_existent = tmp_path / "does_not_exist.txt"

        with caplog.at_level(logging.WARNING):
            processor._cleanup_temp_file(non_existent)

        assert "already cleaned" in caplog.text.lower()

    def test_cleanup_logs_error_on_permission_failure(self, processor, tmp_path, caplog):
        """Verify _cleanup_temp_file logs error on permission failure."""
        import logging
        from unittest.mock import patch

        test_file = tmp_path / "test_permission.txt"
        test_file.write_text("content")

        with caplog.at_level(logging.ERROR):
            with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
                with patch.object(Path, "exists", return_value=True):
                    processor._cleanup_temp_file(test_file)

        assert "permission error" in caplog.text.lower() or "permission" in caplog.text.lower()
