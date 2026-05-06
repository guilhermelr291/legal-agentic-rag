"""Chunking domain dependencies."""

from typing import Annotated

from fastapi import Depends

from src.chunking.service import ChunkingService


def get_chunking_service() -> ChunkingService:
    """Factory dependency for ChunkingService."""
    return ChunkingService()


ChunkingDep = Annotated[ChunkingService, Depends(get_chunking_service)]
