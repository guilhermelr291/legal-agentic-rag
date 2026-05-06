"""Embeddings domain dependencies."""

from typing import Annotated

from fastapi import Depends

from src.embeddings.service import EmbeddingsService


def get_embeddings_service() -> EmbeddingsService:
    """Factory dependency for EmbeddingsService."""
    return EmbeddingsService()


EmbeddingsDep = Annotated[EmbeddingsService, Depends(get_embeddings_service)]
