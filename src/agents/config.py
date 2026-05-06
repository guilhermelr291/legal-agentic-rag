"""Agents domain configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentsConfig(BaseSettings):
    """Configuration for agents and LLM services."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTS_",
        env_file=".env",
        extra="ignore",
    )

    # OpenAI Configuration
    OPENAI_API_KEY: str | None = None
    OPENAI_LIGHTWEIGHT_MODEL: str = "gpt-5-nano"
    OPENAI_MODEL_GENERATION: str = "gpt-5-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Tavily Configuration
    TAVILY_API_KEY: str | None = None
    TAVILY_MAX_RESULTS: int = 5

    # Cohere Configuration
    COHERE_API_KEY: str | None = None
    COHERE_RERANK_MODEL: str = "rerank-v3.5"

    # Reranker Settings
    RERANK_TOP_K: int = 10

    # Supabase Configuration
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_JWT_SECRET: str | None = None

    # Feature Flags
    GRAPH_RAG_ENABLED: bool = False


agents_settings = AgentsConfig()
