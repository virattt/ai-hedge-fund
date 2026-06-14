"""Shared database handle for the observing-pools workflow.

Re-exports the backend's single ``Base``/``engine``/``SessionLocal`` so there is
exactly one database file across the API and the CLI (no second engine, no CWD
hazard). Adds ``session_scope()`` for transactional CLI/pipeline code.

PRD v4 §8.1 ultimately calls for promoting this module to the *source* of the
shared ``Base`` (with the backend re-exporting it). For the Phase-0 vertical
slice we invert that cheaply: the backend stays the source and ``src/storage``
re-exports it. The full inversion is an expansion-phase (P2) refactor.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

# Single shared Base/engine/session — defined once in the backend, absolute-anchored.
from app.backend.database.connection import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db", "session_scope"]


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on any exception, always closes. Use this in
    CLI/pipeline code; FastAPI routes keep using the ``get_db`` dependency.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
