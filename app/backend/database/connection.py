from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

# Get the backend directory path
BACKEND_DIR = Path(__file__).parent.parent
DATABASE_PATH = BACKEND_DIR / "hedge_fund.db"


def _resolve_database_url() -> str:
    """Prefer a managed database (e.g. Render Postgres) via DATABASE_URL,
    falling back to a local SQLite file for local development."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return f"sqlite:///{DATABASE_PATH}"
    # SQLAlchemy requires the "postgresql://" scheme; some providers emit "postgres://".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


# Database configuration
DATABASE_URL = _resolve_database_url()

# SQLite needs check_same_thread=False; other engines must not receive it.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,  # Recycle stale connections (managed Postgres closes idle ones)
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 