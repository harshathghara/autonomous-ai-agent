"""Builds PostgreSQL connection URLs from DATABASE_URL or DB_* env vars."""

import os
from urllib.parse import quote_plus


def build_database_url() -> str:
    if url := os.getenv("DATABASE_URL"):
        return url
    user = os.environ["DB_USER"]
    password = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def build_sync_database_url() -> str:
    return build_database_url().replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
