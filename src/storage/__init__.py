"""Shared persistence layer for the observing-pools workflow.

This package is the single import surface for CLI/pipeline code that needs the
database, so `src/` modules never reach into `app.backend` directly for engine
setup. It re-exports the one shared SQLAlchemy `Base`/engine/session that the
backend already defines (absolute-path-anchored at ``app/backend/hedge_fund.db``),
and aggregates the observing-pool models so a single import registers every
table (PRD v4 §8.1 model-discovery pattern).
"""

from src.storage.database import Base, SessionLocal, engine, get_db, session_scope

__all__ = ["Base", "SessionLocal", "engine", "get_db", "session_scope"]
