"""SQLAlchemy ORM models for documents domain.

Defines Document and Chunk models with:
- Proper naming conventions (singular table names)
- Foreign key relationships
- Indexed columns for RLS (user_id)
- pgvector support for embeddings
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.database import Base


class Document(Base):
    """Document record model.

    Stores metadata about uploaded documents and their processing status.
    RLS is enforced via user_id filtering.
    """

    __tablename__ = "document"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    user_id: Mapped[str] = mapped_column(
        String,
        index=True,
        nullable=False,
        comment="RLS user identifier",
    )
    filename: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Original filename",
    )
    file_type: Mapped[str] = mapped_column(
        ENUM("pdf", "docx", "xlsx", name="document_file_type"),
        nullable=False,
        comment="Document type",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )
    storage_path: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Path in Supabase Storage: {user_id}/{document_id}/{filename}",
    )
    status: Mapped[str] = mapped_column(
        ENUM("processing", "ready", "failed", name="document_status"),
        nullable=False,
        default="processing",
        comment="Current processing status",
    )
    error_msg: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if processing failed",
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="JSONB metadata (XLSX info, graph status)",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default="timezone('utc', now())",
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default="timezone('utc', now())",
        onupdate="timezone('utc', now())",
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Timestamp when processing completed",
    )

    # Relationship to chunks
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Chunk(Base):
    """Chunk record model with embeddings.

    Stores text chunks extracted from documents with their embeddings
    and metadata for retrieval. RLS is enforced via user_id filtering.
    """

    __tablename__ = "chunk"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to documents table",
    )
    user_id: Mapped[str] = mapped_column(
        String,
        index=True,
        nullable=False,
        comment="RLS user identifier",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential index within document",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Chunk text content",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="1536-dim OpenAI embedding vector",
    )
    section_hint: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Detected heading (e.g., 'Clause 12', 'Article 5')",
    )
    section_path: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="Hierarchy breadcrumbs",
    )
    page_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Starting page number",
    )
    page_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Ending page number",
    )
    anchors: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="Detected references in text",
    )
    char_start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Start character offset",
    )
    char_end: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="End character offset",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default="timezone('utc', now())",
        nullable=False,
    )

    # Relationship to document
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )

    __table_args__ = (
        # Unique constraint for upsert operations (document_id, chunk_index)
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="chunk_document_id_chunk_index_key",
        ),
    )
