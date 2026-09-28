"""Central configuration via environment variables (12-factor style).

All settings are read once at import time via pydantic-settings. See
backend/.env.example for documentation of every variable.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM (SECRET) ---
    llm_api_key: str = ""  # Groq API key; empty -> extractive mock provider
    llm_model: str = "openai/gpt-oss-120b"

    # --- Embeddings / vector search ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    top_k: int = 4  # default Top-K retrieved chunks
    max_chunks_per_doc: int = 1200

    # --- Upload limits ---
    max_upload_mb: int = 10
    allowed_upload_types: str = "pdf,txt,md"  # comma-separated

    # --- CORS (PUBLIC) ---
    allowed_origins: str = "http://localhost:3000"

    # --- Logging ---
    log_level: str = "INFO"

    # --- Groq request behaviour ---
    llm_timeout_seconds: float = 25.0
    llm_max_retries: int = 1

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowed_types_list(self) -> list[str]:
        return [t.strip().lower() for t in self.allowed_upload_types.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
