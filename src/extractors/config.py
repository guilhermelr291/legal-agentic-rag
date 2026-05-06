"""Extractors domain configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractorsConfig(BaseSettings):
    """Configuration for document text extraction."""

    model_config = SettingsConfigDict(
        env_prefix="EXTRACTORS_",
        env_file=".env",
        extra="ignore",
    )


extractors_settings = ExtractorsConfig()
