from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./smart_food.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    chroma_persist_directory: str = "./var/chroma"
    internal_api_base_url: str = "http://127.0.0.1:8000"
    internal_api_secret: str = ""
    chat_requests_per_minute: int = 20
    upload_requests_per_minute: int = 5
    upload_max_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
