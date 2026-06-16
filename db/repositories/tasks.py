"""Repository for agent_tasks — create tasks and mark them completed."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentStep, AgentTask


async def create_task(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    input_text: str,
    status: str = "running",
) -> AgentTask:
    task = AgentTask(user_id=user_id, input=input_text, status=status)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def complete_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    *,
    final_output: str,
    status: str = "completed",
) -> AgentTask | None:
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        return None
    task.final_output = final_output
    task.status = status
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task_by_id(db: AsyncSession, task_id: uuid.UUID) -> AgentTask | None:
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    return result.scalar_one_or_none()


async def fail_task(db: AsyncSession, task_id: uuid.UUID, *, error: str) -> AgentTask | None:
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        return None
    task.status = "failed"
    task.final_output = error
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return task


async def reset_task_running(db: AsyncSession, task_id: uuid.UUID) -> AgentTask | None:
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        return None
    task.status = "running"
    task.final_output = None
    task.completed_at = None
    await db.commit()
    await db.refresh(task)
    return task


async def get_tasks_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[AgentTask]:
    last_step_at = (
        select(func.max(AgentStep.created_at))
        .where(AgentStep.task_id == AgentTask.id)
        .correlate(AgentTask)
        .scalar_subquery()
    )
    result = await db.execute(
        select(AgentTask)
        .where(AgentTask.user_id == user_id)
        .order_by(func.coalesce(last_step_at, AgentTask.completed_at, AgentTask.created_at).desc())
    )
    return list(result.scalars().all())


async def get_user_turn_counts(db: AsyncSession, task_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Return total user messages per chat session (opening prompt + follow-ups)."""
    if not task_ids:
        return {}
    result = await db.execute(
        select(AgentStep.task_id, func.count())
        .where(AgentStep.task_id.in_(task_ids), AgentStep.step_type == "user")
        .group_by(AgentStep.task_id)
    )
    followups = {row[0]: int(row[1]) for row in result.all()}
    return {task_id: 1 + followups.get(task_id, 0) for task_id in task_ids}


async def delete_task(db: AsyncSession, task_id: uuid.UUID, *, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return False
    await db.delete(task)
    await db.commit()
    return True


async def mark_stale_running_tasks_failed(db: AsyncSession) -> int:
    """Mark orphaned running tasks as failed after a server restart."""
    result = await db.execute(select(AgentTask).where(AgentTask.status == "running"))
    tasks = list(result.scalars().all())
    if not tasks:
        return 0
    now = datetime.now(timezone.utc)
    message = "Interrupted — server restarted before the task finished."
    for task in tasks:
        task.status = "failed"
        task.final_output = message
        task.completed_at = now
    await db.commit()
    return len(tasks)
