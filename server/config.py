"""Runtime configuration for the FastAPI server.

Sourced from environment variables (see ``.env.example``). All settings are
prefixed with ``AHF_`` (Ai Hedge Fund) so they don't collide with the existing
LLM/data API keys read by ``src/llm/models.py`` and ``src/tools/api.py``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level server settings."""

    model_config = SettingsConfigDict(
        env_prefix="AHF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Auth
    app_token: str | None = Field(
        default=None,
        description="Single-user bearer token. Generate: openssl rand -hex 32. "
        "If unset in F1, server runs in 'open' mode for local dev.",
    )

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173",
        description="Comma-separated list of allowed CORS origins.",
    )

    # Database
    db_url: str = Field(
        default="sqlite:///./data/runs.db",
        description="SQLAlchemy/SQLModel database URL.",
    )

    # Observability
    log_level: str = Field(default="INFO", description="DEBUG | INFO | WARNING | ERROR")
    log_json: bool = Field(default=False, description="Emit logs as JSON.")

    # Concurrency / safety
    max_concurrent_runs: int = Field(default=4)
    sse_keepalive_seconds: int = Field(default=15)

    # File system
    data_dir: Path = Field(default=Path("./data"))

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
