"""Repository for oauth_tokens — store encrypted Google OAuth credentials."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import OAuthToken


async def get_token_row(db: AsyncSession, user_id: uuid.UUID) -> OAuthToken | None:
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    access_token: str,
    refresh_token: str,
    token_expiry: datetime,
    scopes: list[str],
) -> OAuthToken:
    row = await get_token_row(db, user_id)
    if row is None:
        row = OAuthToken(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            scopes=scopes,
        )
        db.add(row)
    else:
        row.access_token = access_token
        row.refresh_token = refresh_token
        row.token_expiry = token_expiry
        row.scopes = scopes
        row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row
