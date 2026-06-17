from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Railway Postgres: fix the scheme if needed (Railway uses postgres://, SQLAlchemy needs postgresql://)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # Local dev: SQLite
    BACKEND_DIR = Path(__file__).parent.parent
    DATABASE_PATH = BACKEND_DIR / "hedge_fund.db"
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
