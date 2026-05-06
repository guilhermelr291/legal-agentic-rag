"""Embeddings domain configuration (OpenAI)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingsConfig(BaseSettings):
    """Configuration for OpenAI embedding generation."""

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDINGS_",
        env_file=".env",
        extra="ignore",
    )

    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    BATCH_SIZE: int = 100
    REQUEST_TIMEOUT: int = 30


embeddings_settings = EmbeddingsConfig()
