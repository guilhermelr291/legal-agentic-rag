from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonConfig(BaseSettings):
    """Shared settings across domains (environment, debug, logging)."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/agentic_rag"


# Exported singleton instance
common_settings = CommonConfig()
