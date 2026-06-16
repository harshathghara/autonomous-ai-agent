"""Repository for agent_steps — persist each thought/tool call/observation (Week 3+)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentStep


async def create_step(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    step_number: int,
    step_type: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
    tool_output: str | None = None,
    reasoning: str | None = None,
) -> AgentStep:
    step = AgentStep(
        task_id=task_id,
        step_number=step_number,
        step_type=step_type,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        reasoning=reasoning,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def get_steps_for_task(db: AsyncSession, task_id: uuid.UUID) -> list[AgentStep]:
    result = await db.execute(
        select(AgentStep).where(AgentStep.task_id == task_id).order_by(AgentStep.step_number)
    )
    return list(result.scalars().all())
