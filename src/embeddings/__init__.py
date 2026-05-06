"""Embeddings domain for OpenAI embedding generation."""

from src.embeddings.config import EmbeddingsConfig, embeddings_settings
from src.embeddings.dependencies import EmbeddingsDep, get_embeddings_service
from src.embeddings.service import EmbeddingsService

__all__ = [
    "EmbeddingsConfig",
    "embeddings_settings",
    "EmbeddingsService",
    "EmbeddingsDep",
    "get_embeddings_service",
]
