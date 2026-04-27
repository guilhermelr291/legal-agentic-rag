"""Database repository layer for document ingestion.

Provides type-safe repository classes for documents and chunks with
RLS-aware operations via SupabaseClient.
"""

from services.db.repositories import (
    ChunkRecord,
    ChunkRepository,
    DocumentCreate,
    DocumentRecord,
    DocumentRepository,
)

__all__ = [
    "ChunkRecord",
    "ChunkRepository",
    "DocumentCreate",
    "DocumentRecord",
    "DocumentRepository",
]
