"""Long-term user memory — load/save preferences in agent_memory (PostgreSQL)."""

import re
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from auth.token_store import default_user_id
from db.models import AgentMemory
from db.url import build_sync_database_url

_sync_engine = None
_MEMORY_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(build_sync_database_url(), pool_pre_ping=True)
    return _sync_engine


def validate_memory_key(key: str) -> str:
    cleaned = key.strip().lower().replace(" ", "_").replace("-", "_")
    if not _MEMORY_KEY_RE.match(cleaned):
        raise ValueError(
            "memory_key must start with a letter and use only lowercase letters, digits, and underscores"
        )
    return cleaned


def list_memories_sync(user_id: uuid.UUID | None = None) -> list[dict]:
    user_id = user_id or default_user_id()
    with Session(_get_sync_engine()) as session:
        rows = session.execute(select(AgentMemory).where(AgentMemory.user_id == user_id)).scalars().all()
        return [
            {"memory_key": row.memory_key, "value": row.value, "source": row.source}
            for row in rows
        ]


def upsert_memory_sync(
    memory_key: str,
    value: str,
    *,
    user_id: uuid.UUID | None = None,
    source: str | None = None,
) -> dict:
    user_id = user_id or default_user_id()
    key = validate_memory_key(memory_key)
    cleaned_value = value.strip()
    if not cleaned_value:
        raise ValueError("value must not be empty")

    with Session(_get_sync_engine()) as session:
        stmt = (
            insert(AgentMemory)
            .values(user_id=user_id, memory_key=key, value=cleaned_value, source=source)
            .on_conflict_do_update(
                constraint="uq_agent_memory_user_key",
                set_={"value": cleaned_value, "source": source},
            )
            .returning(AgentMemory)
        )
        session.execute(stmt)
        session.commit()

    return {"memory_key": key, "value": cleaned_value, "source": source}


def delete_memory_sync(memory_key: str, *, user_id: uuid.UUID | None = None) -> dict:
    user_id = user_id or default_user_id()
    key = validate_memory_key(memory_key)
    with Session(_get_sync_engine()) as session:
        row = session.execute(
            select(AgentMemory).where(
                AgentMemory.user_id == user_id,
                AgentMemory.memory_key == key,
            )
        ).scalar_one_or_none()
        if row is None:
            return {
                "status": "error",
                "error": f"No memory found for key '{key}'. Run memory_read first.",
                "memory_key": key,
            }
        session.delete(row)
        session.commit()
    return {"status": "deleted", "memory_key": key}


def format_memories_for_prompt(user_id: uuid.UUID | None = None) -> str:
    memories = list_memories_sync(user_id)
    if not memories:
        return ""
    lines = "\n".join(f"- {m['memory_key']}: {m['value']}" for m in memories)
    return f"\n\nKnown user preferences (from memory):\n{lines}"
