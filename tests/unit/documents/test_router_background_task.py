"""Unit tests for document router background task integration.

Tests verify:
- trigger_document_processing initializes all required services
- DocumentProcessor is instantiated with correct dependencies
- processor.process() is called with correct arguments
- Database session is properly managed (created, committed, rolled back on error)
- StorageService is created using from_service_role factory
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@pytest.fixture(autouse=True)
def clear_imports():
    """Clear router module imports to ensure fresh imports in tests."""
    import sys

    # Remove the module from cache if it exists
    modules_to_remove = [
        key for key in sys.modules.keys() if key.startswith("src.documents.router")
    ]
    for mod in modules_to_remove:
        del sys.modules[mod]


class TestTriggerDocumentProcessing:
    """Tests for the trigger_document_processing background task function."""

    @pytest.fixture
    def mock_session_factory(self):
        """Create a mock SessionFactory that yields a mock session."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.flush = AsyncMock()

        # Create an async context manager mock
        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        return mock_context_manager, mock_session

    @pytest.fixture
    def mock_storage_service(self):
        """Create a mock StorageService."""
        storage = MagicMock()
        storage.download_to_path = AsyncMock()
        return storage

    @pytest.fixture
    def mock_extraction_service(self):
        """Create a mock ExtractionService."""
        extraction = MagicMock()
        extraction.extract_text = AsyncMock()
        extraction.extract_metadata = AsyncMock()
        return extraction

    @pytest.fixture
    def mock_chunking_service(self):
        """Create a mock ChunkingService."""
        chunking = MagicMock()
        chunking.chunk = Mock(return_value=[])
        return chunking

    @pytest.fixture
    def mock_embeddings_service(self):
        """Create a mock EmbeddingsService."""
        embeddings = MagicMock()
        embeddings.generate_embeddings = AsyncMock(return_value=[])
        embeddings.generate_single = AsyncMock(return_value=[])
        return embeddings

    @pytest.fixture
    def mock_document_processor(self):
        """Create a mock DocumentProcessor."""
        processor = MagicMock()
        processor.process = AsyncMock()
        return processor

    @pytest.mark.asyncio
    async def test_all_services_initialized(
        self,
        mock_session_factory,
        mock_storage_service,
        mock_extraction_service,
        mock_chunking_service,
        mock_embeddings_service,
    ):
        """Verify all required services are initialized in background task."""
        mock_context_manager, mock_session = mock_session_factory

        # Import the module under test first
        from src.documents import router as router_module

        with (
            patch.object(router_module, "SessionFactory", return_value=mock_context_manager),
            patch.object(
                router_module.StorageService,
                "from_service_role",
                new_callable=AsyncMock,
                return_value=mock_storage_service,
            ) as mock_storage_factory,
            patch.object(
                router_module,
                "ExtractionService",
                return_value=mock_extraction_service,
            ) as mock_extraction_cls,
            patch.object(
                router_module,
                "ChunkingService",
                return_value=mock_chunking_service,
            ) as mock_chunking_cls,
            patch.object(
                router_module,
                "EmbeddingsService",
                return_value=mock_embeddings_service,
            ) as mock_embeddings_cls,
            patch.object(
                router_module,
                "DocumentProcessor",
            ) as mock_processor_cls,
        ):
            # Execute
            await router_module.trigger_document_processing("doc-123", "user-456")

            # Verify all services were initialized
            mock_storage_factory.assert_called_once()
            mock_extraction_cls.assert_called_once()
            mock_chunking_cls.assert_called_once()
            mock_embeddings_cls.assert_called_once()

            # Verify DocumentProcessor was instantiated with all services
            mock_processor_cls.assert_called_once()
            call_kwargs = mock_processor_cls.call_args[1]
            assert call_kwargs["storage"] == mock_storage_service
            assert call_kwargs["extraction"] == mock_extraction_service
            assert call_kwargs["chunking"] == mock_chunking_service
            assert call_kwargs["embeddings"] == mock_embeddings_service
            assert call_kwargs["db"] == mock_session

    @pytest.mark.asyncio
    async def test_processor_called_with_correct_arguments(
        self,
        mock_session_factory,
        mock_storage_service,
        mock_extraction_service,
        mock_chunking_service,
        mock_embeddings_service,
        mock_document_processor,
    ):
        """Verify processor.process() is called with document_id and user_id."""
        mock_context_manager, _ = mock_session_factory

        from src.documents import router as router_module

        with (
            patch.object(router_module, "SessionFactory", return_value=mock_context_manager),
            patch.object(
                router_module.StorageService,
                "from_service_role",
                new_callable=AsyncMock,
                return_value=mock_storage_service,
            ),
            patch.object(router_module, "ExtractionService", return_value=mock_extraction_service),
            patch.object(router_module, "ChunkingService", return_value=mock_chunking_service),
            patch.object(router_module, "EmbeddingsService", return_value=mock_embeddings_service),
            patch.object(
                router_module,
                "DocumentProcessor",
                return_value=mock_document_processor,
            ),
        ):
            # Execute
            await router_module.trigger_document_processing("doc-123", "user-456")

            # Verify processor.process was called with correct args
            mock_document_processor.process.assert_called_once_with("doc-123", "user-456")

    @pytest.mark.asyncio
    async def test_database_session_committed_on_success(
        self,
        mock_session_factory,
        mock_storage_service,
        mock_extraction_service,
        mock_chunking_service,
        mock_embeddings_service,
        mock_document_processor,
    ):
        """Verify database session is committed after successful processing."""
        mock_context_manager, mock_session = mock_session_factory

        from src.documents import router as router_module

        with (
            patch.object(router_module, "SessionFactory", return_value=mock_context_manager),
            patch.object(
                router_module.StorageService,
                "from_service_role",
                new_callable=AsyncMock,
                return_value=mock_storage_service,
            ),
            patch.object(router_module, "ExtractionService", return_value=mock_extraction_service),
            patch.object(router_module, "ChunkingService", return_value=mock_chunking_service),
            patch.object(router_module, "EmbeddingsService", return_value=mock_embeddings_service),
            patch.object(
                router_module,
                "DocumentProcessor",
                return_value=mock_document_processor,
            ),
        ):
            # Execute
            await router_module.trigger_document_processing("doc-123", "user-456")

            # Verify session was committed
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_session_rolled_back_on_error(
        self,
        mock_session_factory,
        mock_storage_service,
        mock_extraction_service,
        mock_chunking_service,
        mock_embeddings_service,
    ):
        """Verify database session is rolled back when processing fails."""
        mock_context_manager, mock_session = mock_session_factory

        # Create a processor that raises an exception
        failing_processor = MagicMock()
        failing_processor.process = AsyncMock(side_effect=Exception("Processing failed"))

        from src.documents import router as router_module

        with (
            patch.object(router_module, "SessionFactory", return_value=mock_context_manager),
            patch.object(
                router_module.StorageService,
                "from_service_role",
                new_callable=AsyncMock,
                return_value=mock_storage_service,
            ),
            patch.object(router_module, "ExtractionService", return_value=mock_extraction_service),
            patch.object(router_module, "ChunkingService", return_value=mock_chunking_service),
            patch.object(router_module, "EmbeddingsService", return_value=mock_embeddings_service),
            patch.object(
                router_module,
                "DocumentProcessor",
                return_value=failing_processor,
            ),
        ):
            # Execute - should not raise because errors are caught
            await router_module.trigger_document_processing("doc-123", "user-456")

            # Verify session was rolled back
            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_storage_service_created_with_service_role(
        self,
        mock_session_factory,
    ):
        """Verify StorageService is created using from_service_role factory method."""
        mock_context_manager, _ = mock_session_factory

        from src.documents import router as router_module

        with (
            patch.object(router_module, "SessionFactory", return_value=mock_context_manager),
            patch.object(
                router_module.StorageService,
                "from_service_role",
                new_callable=AsyncMock,
            ) as mock_storage_factory,
            patch.object(router_module, "ExtractionService"),
            patch.object(router_module, "ChunkingService"),
            patch.object(router_module, "EmbeddingsService"),
            patch.object(router_module, "DocumentProcessor"),
        ):
            # Execute
            await router_module.trigger_document_processing("doc-123", "user-456")

            # Verify StorageService.from_service_role was called
            mock_storage_factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_isolated_db_session_created(
        self,
        mock_session_factory,
    ):
        """Verify isolated DB session is created using SessionFactory."""
        mock_context_manager, _ = mock_session_factory

        from src.documents import router as router_module

        with (
            patch.object(
                router_module,
                "SessionFactory",
                return_value=mock_context_manager,
            ) as mock_session_factory_patch,
            patch.object(
                router_module.StorageService,
                "from_service_role",
                new_callable=AsyncMock,
            ),
            patch.object(router_module, "ExtractionService"),
            patch.object(router_module, "ChunkingService"),
            patch.object(router_module, "EmbeddingsService"),
            patch.object(router_module, "DocumentProcessor"),
        ):
            # Execute
            await router_module.trigger_document_processing("doc-123", "user-456")

            # Verify SessionFactory was called
            mock_session_factory_patch.assert_called_once()


class TestUploadEndpointBackgroundTaskIntegration:
    """Tests for upload endpoint background task integration."""

    @pytest.mark.asyncio
    async def test_upload_endpoint_returns_201_immediately(self):
        """Verify upload endpoint returns 201 without waiting for processing."""
        from fastapi import BackgroundTasks

        from src.documents import router as router_module
        from src.documents.router import upload_document

        # Create mocks
        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"test content")
        mock_file.content_type = "application/pdf"

        mock_background_tasks = MagicMock(spec=BackgroundTasks)
        mock_background_tasks.add_task = Mock()

        mock_user_id = "user-456"

        # Mock database and storage
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()

        mock_storage = MagicMock()
        mock_storage.upload_file = AsyncMock()

        # Mock document service
        mock_doc = MagicMock()
        mock_doc.id = "doc-123"
        mock_doc.filename = "test.pdf"
        mock_doc.file_type = "pdf"
        mock_doc.file_size = 12
        mock_doc.storage_path = "user-456/doc-123/test.pdf"
        mock_doc.status = "processing"
        mock_doc.created_at = None

        with (
            patch.object(router_module, "DocumentService") as mock_service_cls,
            patch.object(router_module, "uuid") as mock_uuid_module,
            patch.object(router_module, "validate_file_extension", return_value="pdf"),
            patch.object(router_module, "validate_file_size"),
        ):
            mock_uuid_module.uuid4.return_value = "doc-123"
            mock_service = MagicMock()
            mock_service.create = AsyncMock(return_value=mock_doc)
            mock_service_cls.return_value = mock_service

            # Execute
            response = await upload_document(
                background_tasks=mock_background_tasks,
                file=mock_file,
                user_id=mock_user_id,
                db=mock_db,
                storage=mock_storage,
            )

            # Verify response is 201 and returned immediately
            assert response.document_id == "doc-123"
            assert response.status == "processing"

            # Verify background task was added
            mock_background_tasks.add_task.assert_called_once()
            call_args = mock_background_tasks.add_task.call_args
            assert call_args[0][0].__name__ == "trigger_document_processing"
            assert call_args[1]["document_id"] == "doc-123"
            assert call_args[1]["user_id"] == "user-456"

    @pytest.mark.asyncio
    async def test_background_task_added_with_correct_function(self):
        """Verify background task is added with trigger_document_processing function."""
        from fastapi import BackgroundTasks

        from src.documents import router as router_module
        from src.documents.router import trigger_document_processing, upload_document

        # Create mocks
        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"test content")
        mock_file.content_type = "application/pdf"

        mock_background_tasks = MagicMock(spec=BackgroundTasks)
        mock_background_tasks.add_task = Mock()

        mock_user_id = "user-456"
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()

        mock_storage = MagicMock()
        mock_storage.upload_file = AsyncMock()

        mock_doc = MagicMock()
        mock_doc.id = "doc-123"
        mock_doc.filename = "test.pdf"
        mock_doc.file_type = "pdf"
        mock_doc.file_size = 12
        mock_doc.storage_path = "user-456/doc-123/test.pdf"
        mock_doc.status = "processing"
        mock_doc.created_at = None

        with (
            patch.object(router_module, "DocumentService") as mock_service_cls,
            patch.object(router_module, "uuid") as mock_uuid_module,
            patch.object(router_module, "validate_file_extension", return_value="pdf"),
            patch.object(router_module, "validate_file_size"),
        ):
            mock_uuid_module.uuid4.return_value = "doc-123"
            mock_service = MagicMock()
            mock_service.create = AsyncMock(return_value=mock_doc)
            mock_service_cls.return_value = mock_service

            # Execute
            await upload_document(
                background_tasks=mock_background_tasks,
                file=mock_file,
                user_id=mock_user_id,
                db=mock_db,
                storage=mock_storage,
            )

            # Verify the correct function is passed to add_task
            mock_background_tasks.add_task.assert_called_once()
            call_args = mock_background_tasks.add_task.call_args
            assert call_args[0][0] == trigger_document_processing
