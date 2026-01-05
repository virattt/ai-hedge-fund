from logging.config import fileConfig
import os
from urllib.parse import quote_plus
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set database URL from environment variable or fallback to SQLite
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
                    
                    database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
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
    BACKEND_DIR = Path(__file__).parent.parent.parent
    DATABASE_PATH = BACKEND_DIR / "hedge_fund.db"
    database_url = f"sqlite:///{DATABASE_PATH}"

# Override sqlalchemy.url in config
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.backend.database.models import Base
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
