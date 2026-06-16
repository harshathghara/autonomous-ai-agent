"""Repository for agent_memory — long-term user facts keyed by memory_key (Week 4+)."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentMemory


async def upsert_memory(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    memory_key: str,
    value: str,
    source: str | None = None,
) -> AgentMemory:
    stmt = (
        insert(AgentMemory)
        .values(user_id=user_id, memory_key=memory_key, value=value, source=source)
        .on_conflict_do_update(
            constraint="uq_agent_memory_user_key",
            set_={"value": value, "source": source},
        )
        .returning(AgentMemory)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()


async def get_memories_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[AgentMemory]:
    result = await db.execute(select(AgentMemory).where(AgentMemory.user_id == user_id))
    return list(result.scalars().all())
