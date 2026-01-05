from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
from urllib.parse import quote_plus

# Get the backend directory path
BACKEND_DIR = Path(__file__).parent.parent
DATABASE_PATH = BACKEND_DIR / "hedge_fund.db"

# Database configuration - PostgreSQL or SQLite fallback
POSTGRES_URI = os.getenv("POSTGRES_URI")

if POSTGRES_URI:
    # Parse POSTGRES_URI format: user:password@host:port/database
    # Convert to SQLAlchemy format: postgresql://user:password@host:port/database
    try:
        if "@" in POSTGRES_URI and "/" in POSTGRES_URI:
            # Split into credentials@host:port and database
            parts = POSTGRES_URI.split("@", 1)
            if len(parts) == 2:
                credentials = parts[0]
                host_db = parts[1]
                
                # Split credentials into user and password
                if ":" in credentials:
                    user, password = credentials.split(":", 1)
                    user = quote_plus(user)
                    password = quote_plus(password)
                else:
                    user = quote_plus(credentials)
                    password = ""
                
                # Split host_db into host:port and database
                if "/" in host_db:
                    host_port, database = host_db.split("/", 1)
                    if ":" in host_port:
                        host, port = host_port.split(":", 1)
                    else:
                        host = host_port
                        port = "5432"
                    
                    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{database}"
                else:
                    raise ValueError("POSTGRES_URI must include database name after /")
            else:
                raise ValueError("Invalid POSTGRES_URI format")
        else:
            raise ValueError("POSTGRES_URI must be in format user:password@host:port/database")
    except Exception as e:
        print(f"Error parsing POSTGRES_URI: {e}. Falling back to SQLite.")
        POSTGRES_URI = None

if not POSTGRES_URI:
    # Fallback to SQLite
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    connect_args = {"check_same_thread": False}  # Needed for SQLite
else:
    connect_args = {}  # No special args needed for PostgreSQL

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
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