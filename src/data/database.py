"""
Database configuration for MySQL cache layer.

Supports both SQLite (for development) and MySQL (for production).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import logging

logger = logging.getLogger(__name__)

# Create Base class for cache models
Base = declarative_base()

# Get DATABASE_URL from environment or use SQLite default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cache.db")

# Determine if using SQLite for specific configuration
is_sqlite = DATABASE_URL.startswith("sqlite")

# Create engine with appropriate settings
if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,  # SQLite doesn't need connection pooling
        echo=False,
    )
    logger.info(f"Using SQLite database: {DATABASE_URL}")
else:
    # MySQL/PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=False,
    )
    logger.info(f"Using MySQL database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'configured'}")

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency function for getting database sessions.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables.

    Creates all tables defined in models if they don't exist.
    Should be called during application startup.
    """
    # Import models here to avoid circular imports
    from src.data.mysql_models import StockPrice, FinancialMetric, CompanyNewsItem

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")


def get_session():
    """
    Get a new database session.

    Returns:
        Session: SQLAlchemy database session

    Note: Caller is responsible for closing the session.
    """
    return SessionLocal()
