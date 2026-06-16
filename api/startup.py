"""Startup checks and housekeeping for the FastAPI app."""

import os

REQUIRED_ENV_VARS = (
    "TOKEN_ENCRYPTION_KEY",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "TAVILY_API_KEY",
)

OPTIONAL_ENV_VARS = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REDIRECT_URI",
    "USER_EMAIL",
    "USER_TIMEZONE",
    "DATABASE_URL",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
)


def validate_env() -> list[str]:
    """Return list of missing required environment variables."""
    return [name for name in REQUIRED_ENV_VARS if not os.getenv(name, "").strip()]


def auto_migrate_enabled() -> bool:
    return os.getenv("AUTO_MIGRATE", "true").strip().lower() in ("1", "true", "yes")
