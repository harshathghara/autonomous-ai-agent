"""Alembic migration runtime — connects to PostgreSQL and runs schema upgrades."""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

from db.base import Base
from db.url import build_sync_database_url

load_dotenv()

config = context.config
database_url = build_sync_database_url()

# Skip when called from FastAPI startup — fileConfig() would hide Uvicorn's URL log.
if config.config_file_name is not None and not os.environ.get("_ALEMBIC_EMBEDDED"):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
