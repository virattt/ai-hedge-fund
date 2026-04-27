"""Database engine + session lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqlmodel import Session, SQLModel, create_engine

from ..config import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

_settings = get_settings()


def _ensure_dir_for_sqlite(url: str) -> None:
    if url.startswith("sqlite:///"):
        path = Path(url.removeprefix("sqlite:///"))
        path.parent.mkdir(parents=True, exist_ok=True)


_ensure_dir_for_sqlite(_settings.db_url)

engine = create_engine(
    _settings.db_url,
    echo=False,
    connect_args=({"check_same_thread": False} if _settings.db_url.startswith("sqlite") else {}),
)


def init_db() -> None:
    """Create all tables (used in tests; prod uses Alembic)."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(engine) as session:
        yield session
