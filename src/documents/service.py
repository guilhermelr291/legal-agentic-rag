"""Documents domain service for database operations.

Provides CRUD operations for documents using SQLAlchemy async patterns.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.models import Chunk, Document

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document database operations.

    Provides CRUD operations and status management for documents
    using SQLAlchemy 2.0 async API.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: Async SQLAlchemy session.
        """
        self._db = db

    async def create(
        self,
        user_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        storage_path: str,
        status: str = "processing",
    ) -> Document:
        """Create a new document record.

        Args:
            user_id: Owner user ID.
            filename: Original filename.
            file_type: File type (pdf, docx, xlsx).
            file_size: File size in bytes.
            storage_path: Path in storage bucket.
            status: Initial status (default: processing).

        Returns:
            Created Document model instance.
        """
        document = Document(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            status=status,
        )
        self._db.add(document)
        await self._db.flush()
        await self._db.refresh(document)
        return document

    async def get_by_id(self, document_id: str, user_id: str) -> Document | None:
        """Get document by ID with user ownership check.

        Args:
            document_id: Document UUID.
            user_id: User ID for RLS enforcement.

        Returns:
            Document if found and owned by user, None otherwise.
        """
        result = await self._db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        status: str | None = None,
    ) -> list[Document]:
        """List all documents for a user.

        Args:
            user_id: User ID to filter by.
            status: Optional status filter.

        Returns:
            List of Document model instances, ordered by created_at desc.
        """
        query = select(Document).where(Document.user_id == user_id)

        if status:
            query = query.where(Document.status == status)

        query = query.order_by(Document.created_at.desc())

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        document_id: str,
        user_id: str,
        status: str,
        error_msg: str | None = None,
    ) -> Document | None:
        """Update document status.

        Args:
            document_id: Document UUID.
            user_id: User ID for RLS enforcement.
            status: New status value.
            error_msg: Optional error message for failed status.

        Returns:
            Updated Document if found, None otherwise.
        """
        values: dict[str, Any] = {"status": status}
        if error_msg:
            values["error_msg"] = error_msg
        if status == "ready":
            values["processed_at"] = datetime.now(UTC)

        result = await self._db.execute(
            update(Document)
            .where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
            .values(**values)
            .returning(Document)
        )
        await self._db.flush()
        return result.scalar_one_or_none()

    async def update_meta(
        self,
        document_id: str,
        user_id: str,
        meta: dict[str, Any],
    ) -> Document | None:
        """Update document metadata (merges with existing).

        Args:
            document_id: Document UUID.
            user_id: User ID for RLS enforcement.
            meta: Metadata dict to merge into existing meta.

        Returns:
            Updated Document if found, None otherwise.
        """
        # First get existing meta
        doc = await self.get_by_id(document_id, user_id)
        if not doc:
            return None

        # Merge meta
        existing_meta = doc.meta or {}
        existing_meta.update(meta)

        result = await self._db.execute(
            update(Document)
            .where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
            .values(meta=existing_meta)
            .returning(Document)
        )
        await self._db.flush()
        return result.scalar_one_or_none()

    async def delete(self, document_id: str, user_id: str) -> bool:
        """Delete a document.

        Args:
            document_id: Document UUID.
            user_id: User ID for RLS enforcement.

        Returns:
            True if deleted, False if not found.
        """
        result = await self._db.execute(
            delete(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        await self._db.flush()
        return result.rowcount > 0

    async def upsert_chunks(self, chunks: list[dict[str, Any]]) -> int:
        """Upsert chunks for idempotent chunk persistence.

        Uses PostgreSQL upsert (INSERT ... ON CONFLICT DO UPDATE) to insert
        new chunks or update existing ones based on (document_id, chunk_index)
        unique constraint.

        Args:
            chunks: List of chunk dictionaries with keys:
                - document_id: str
                - user_id: str
                - chunk_index: int
                - content: str
                - embedding: list[float] | None
                - section_hint: str | None
                - section_path: list[str]
                - page_start: int | None
                - page_end: int | None
                - anchors: list[str]
                - char_start: int
                - char_end: int

        Returns:
            Number of chunks upserted (inserted or updated).
        """
        if not chunks:
            return 0

        # Build insert statement with all chunk fields
        stmt = (
            pg_insert(Chunk)
            .values(chunks)
            .on_conflict_do_update(
                index_elements=["document_id", "chunk_index"],
                set_={
                    "content": pg_insert(Chunk).excluded.content,
                    "embedding": pg_insert(Chunk).excluded.embedding,
                    "section_hint": pg_insert(Chunk).excluded.section_hint,
                    "section_path": pg_insert(Chunk).excluded.section_path,
                    "page_start": pg_insert(Chunk).excluded.page_start,
                    "page_end": pg_insert(Chunk).excluded.page_end,
                    "anchors": pg_insert(Chunk).excluded.anchors,
                    "char_start": pg_insert(Chunk).excluded.char_start,
                    "char_end": pg_insert(Chunk).excluded.char_end,
                },
            )
        )

        result = await self._db.execute(stmt)
        return result.rowcount


class DocumentsServiceError(Exception):
    """Exception for document service errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


__all__ = [
    "DocumentService",
    "DocumentsServiceError",
]
