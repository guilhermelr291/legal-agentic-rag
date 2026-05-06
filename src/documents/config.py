"""Documents domain configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentsConfig(BaseSettings):
    """Configuration for document processing and validation."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUMENTS_",
        env_file=".env",
        extra="ignore",
    )

    MAX_FILE_SIZE: int = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".xlsx"}
    PROCESSING_TIMEOUT_SECONDS: int = 300


documents_settings = DocumentsConfig()
