import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Ensure backend root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import all SQLAlchemy models so Base.metadata contains complete table schema definitions
from app.core.db import Base
from app.core.config import settings
import app.models.business_data
import app.models.investigation
import app.models.user
import app.models.audit_log

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Dynamically override sqlalchemy.url from application config
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite"):
    # SQLite URL adjustment for Alembic
    config.set_main_option("sqlalchemy.url", db_url)
else:
    config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
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
