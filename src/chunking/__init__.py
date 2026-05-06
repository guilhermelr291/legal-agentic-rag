"""Chunking domain for legal document chunking with structure preservation."""

from src.chunking.config import ChunkingConfig, chunking_settings
from src.chunking.dependencies import ChunkingDep, get_chunking_service
from src.chunking.service import ChunkingService, LegalChunk

__all__ = [
    "ChunkingConfig",
    "chunking_settings",
    "ChunkingService",
    "LegalChunk",
    "ChunkingDep",
    "get_chunking_service",
]
