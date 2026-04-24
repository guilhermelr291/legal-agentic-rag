from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str
    openai_lightweight_model: str = "gpt-5-nano"
    openai_model_generation: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    tavily_api_key: str | None = None
    tavily_max_results: int = 5
    cohere_api_key: str | None = None
    cohere_rerank_model: str = "rerank-v3.5"
    rerank_top_k: int = 10

    # Supabase Configuration
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str | None = None

    # Feature Flags
    graph_rag_enabled: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
