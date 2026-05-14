"""Unit tests for DocumentService.upsert_chunks() method.

Tests idempotent chunk persistence using PostgreSQL upsert.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.service import DocumentService


@pytest.fixture
def mock_db_session() -> AsyncSession:
    """Create a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def document_service(mock_db_session: AsyncSession) -> DocumentService:
    """Provide a DocumentService instance with mock database session."""
    return DocumentService(mock_db_session)


class TestUpsertChunks:
    """Test suite for upsert_chunks method."""

    @pytest.mark.asyncio
    async def test_upsert_chunks_method_exists(
        self,
        document_service: DocumentService,
    ) -> None:
        """Test that upsert_chunks method exists on DocumentService."""
        assert hasattr(document_service, "upsert_chunks")
        assert callable(document_service.upsert_chunks)

    @pytest.mark.asyncio
    async def test_upsert_chunks_is_async(
        self,
        document_service: DocumentService,
    ) -> None:
        """Test that upsert_chunks is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(document_service.upsert_chunks)

    @pytest.mark.asyncio
    async def test_upsert_chunks_accepts_list_of_dicts(
        self,
        document_service: DocumentService,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test that upsert_chunks accepts a list of chunk dictionaries."""
        chunks_data = [
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": 0,
                "content": "Test content",
                "embedding": [0.1] * 1536,
                "section_hint": "Section",
                "section_path": ["Path"],
                "page_start": 1,
                "page_end": 1,
                "anchors": [],
                "char_start": 0,
                "char_end": 12,
            },
        ]

        # Mock the execution result
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        result = await document_service.upsert_chunks(chunks_data)

        # Verify method was called and returned rowcount
        assert result == 1
        assert mock_db_session.execute.called

    @pytest.mark.asyncio
    async def test_uses_database_execute(
        self,
        document_service: DocumentService,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test that upsert uses database session execute."""
        chunks_data = [
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": 0,
                "content": "Test content",
                "embedding": [0.1] * 1536,
                "section_hint": "Section",
                "section_path": [],
                "page_start": 1,
                "page_end": 1,
                "anchors": [],
                "char_start": 0,
                "char_end": 12,
            },
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        await document_service.upsert_chunks(chunks_data)

        # Verify database execute was called
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_accepts_various_field_combinations(
        self,
        document_service: DocumentService,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test that upsert handles various field combinations."""
        # Test with None values for optional fields
        chunks_data = [
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": 0,
                "content": "Test content",
                "embedding": None,
                "section_hint": None,
                "section_path": [],
                "page_start": None,
                "page_end": None,
                "anchors": [],
                "char_start": 0,
                "char_end": 12,
            },
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        result = await document_service.upsert_chunks(chunks_data)

        assert result == 1
        mock_db_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_accepts_all_fields(
        self,
        document_service: DocumentService,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test that upsert accepts all chunk fields."""
        chunks_data = [
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": 0,
                "content": "Updated content",
                "embedding": [0.9] * 1536,
                "section_hint": "Updated Section",
                "section_path": ["Updated", "Path"],
                "page_start": 5,
                "page_end": 6,
                "anchors": ["updated"],
                "char_start": 100,
                "char_end": 115,
            },
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        result = await document_service.upsert_chunks(chunks_data)

        assert result == 1
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_number_of_chunks_upserted(
        self,
        document_service: DocumentService,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test that method returns the number of chunks upserted."""
        chunks_data = [
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": 0,
                "content": "Chunk 0",
                "embedding": None,
                "section_hint": None,
                "section_path": [],
                "page_start": None,
                "page_end": None,
                "anchors": [],
                "char_start": 0,
                "char_end": 7,
            },
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": 1,
                "content": "Chunk 1",
                "embedding": None,
                "section_hint": None,
                "section_path": [],
                "page_start": None,
                "page_end": None,
                "anchors": [],
                "char_start": 8,
                "char_end": 15,
            },
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        result = await document_service.upsert_chunks(chunks_data)

        assert result == 2

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(
        self,
        document_service: DocumentService,
    ) -> None:
        """Test that empty list returns zero without database call."""
        result = await document_service.upsert_chunks([])

        assert result == 0

    @pytest.mark.asyncio
    async def test_multiple_chunks_in_single_call(
        self,
        document_service: DocumentService,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test that multiple chunks can be upserted in a single call."""
        chunks_data = [
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": i,
                "content": f"Chunk {i}",
                "embedding": [0.1 * i] * 1536,
                "section_hint": f"Section {i}",
                "section_path": [f"Path {i}"],
                "page_start": i + 1,
                "page_end": i + 2,
                "anchors": [f"anchor{i}"],
                "char_start": i * 10,
                "char_end": (i * 10) + 8,
            }
            for i in range(5)
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db_session.execute.return_value = mock_result

        result = await document_service.upsert_chunks(chunks_data)

        assert result == 5
        assert mock_db_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_uses_provided_database_session(
        self,
        document_service: DocumentService,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test that method uses the provided database session for execution."""
        chunks_data = [
            {
                "document_id": "doc-123",
                "user_id": "user-456",
                "chunk_index": 0,
                "content": "Test",
                "embedding": None,
                "section_path": [],
                "anchors": [],
                "char_start": 0,
                "char_end": 4,
            },
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        with patch("src.documents.service.pg_insert"):
            await document_service.upsert_chunks(chunks_data)

        # Verify the service's session was used
        mock_db_session.execute.assert_called_once()
