"""Chunking domain configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ChunkingConfig(BaseSettings):
    """Configuration for document chunking."""

    model_config = SettingsConfigDict(
        env_prefix="CHUNKING_",
        env_file=".env",
        extra="ignore",
    )

    DEFAULT_CHUNK_SIZE: int = 1000
    DEFAULT_CHUNK_OVERLAP: int = 100  # 10% of chunk_size


chunking_settings = ChunkingConfig()
