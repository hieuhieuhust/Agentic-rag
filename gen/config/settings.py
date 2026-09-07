from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Multimodal PDF RAG"
    api_base_url: str = "http://127.0.0.1:8000"
    api_secret_key: str = Field(default="change-this-development-secret-key")
    worker_token: str = Field(default="change-this-development-worker-token")

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/multimodal_rag"
    )
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_path: str = "./qdrant_db_local"

    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_bucket: str = "rag-data"

    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    mistral_api_key: str | None = None

    access_token_minutes: int = 1440


@lru_cache
def get_settings() -> Settings:
    return Settings()
