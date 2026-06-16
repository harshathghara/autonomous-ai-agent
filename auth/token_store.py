"""OAuth token helpers — encrypt/decrypt credentials and load/save them in PostgreSQL."""

import os
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db.models import OAuthToken
from db.repositories import tokens as token_repo
from db.url import build_sync_database_url

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

_sync_engine = None


@lru_cache
def _fernet() -> Fernet:
    key = os.environ["TOKEN_ENCRYPTION_KEY"]
    return Fernet(key.encode() if isinstance(key, str) else key)


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(build_sync_database_url(), pool_pre_ping=True)
    return _sync_engine


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt token — check TOKEN_ENCRYPTION_KEY") from exc


def default_user_id() -> UUID:
    return UUID(os.environ["DEFAULT_USER_ID"])


def oauth_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.environ["GOOGLE_REDIRECT_URI"]],
        }
    }
    return Flow.from_client_config(client_config, scopes=GOOGLE_SCOPES)


def credentials_from_tokens(
    access_token: str,
    refresh_token: str,
    token_expiry: datetime,
    scopes: list[str] | None,
) -> Credentials:
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=scopes or GOOGLE_SCOPES,
        expiry=token_expiry.replace(tzinfo=None) if token_expiry.tzinfo else token_expiry,
    )


def _creds_from_row(row: OAuthToken) -> Credentials:
    return credentials_from_tokens(
        access_token=decrypt(row.access_token),
        refresh_token=decrypt(row.refresh_token),
        token_expiry=row.token_expiry,
        scopes=row.scopes,
    )


def _save_row_from_creds(row: OAuthToken, creds: Credentials) -> None:
    expiry = creds.expiry or datetime.now(timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    row.access_token = encrypt(creds.token or "")
    row.refresh_token = encrypt(creds.refresh_token or "")
    row.token_expiry = expiry
    row.scopes = list(creds.scopes or GOOGLE_SCOPES)
    row.updated_at = datetime.now(timezone.utc)


def load_credentials_sync(user_id: UUID | None = None) -> Credentials:
    """Sync token load for LangChain tools (safe inside LangGraph's async executor)."""
    user_id = user_id or default_user_id()
    with Session(_get_sync_engine()) as session:
        row = session.execute(
            select(OAuthToken).where(OAuthToken.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            raise RuntimeError(
                "No Google OAuth tokens found. Run: python -m auth.login_server "
                "then open http://localhost:8000/auth/google"
            )
        creds = _creds_from_row(row)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_row_from_creds(row, creds)
            session.commit()
        return creds


async def save_credentials(db: AsyncSession, user_id: UUID, creds: Credentials) -> None:
    expiry = creds.expiry or datetime.now(timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    await token_repo.upsert_token(
        db,
        user_id=user_id,
        access_token=encrypt(creds.token or ""),
        refresh_token=encrypt(creds.refresh_token or ""),
        token_expiry=expiry,
        scopes=list(creds.scopes or GOOGLE_SCOPES),
    )


async def load_credentials(db: AsyncSession, user_id: UUID) -> Credentials:
    row = await token_repo.get_token_row(db, user_id)
    if row is None:
        raise RuntimeError(
            "No Google OAuth tokens found. Run: python -m auth.login_server "
            "then open http://localhost:8000/auth/google"
        )
    creds = _creds_from_row(row)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        await save_credentials(db, user_id, creds)
    return creds
