from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str
    openai_model_default: str = "gpt-5-nano"
    openai_model_generation: str = "gpt-5-mini"
    tavily_api_key: str | None = None
    tavily_max_results: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
