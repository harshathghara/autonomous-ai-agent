"""Persist agent tasks and steps to PostgreSQL; rebuild state for task resumption."""

import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from auth.token_store import default_user_id
from db.repositories import steps as steps_repo
from db.repositories import tasks as tasks_repo
from db.session import AsyncSessionLocal


def messages_to_langchain(task_input: str, steps: list) -> list[BaseMessage]:
    """Rebuild LangChain message history from stored agent_steps."""
    messages: list[BaseMessage] = [HumanMessage(content=task_input)]
    i = 0
    while i < len(steps):
        step = steps[i]
        if step.step_type == "thought" and step.reasoning:
            messages.append(AIMessage(content=step.reasoning))
        elif step.step_type == "tool_call":
            tool_call_id = f"call_{step.step_number}"
            messages.append(
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": tool_call_id,
                            "name": step.tool_name or "unknown",
                            "args": step.tool_input or {},
                        }
                    ],
                )
            )
            if i + 1 < len(steps) and steps[i + 1].step_type == "observation":
                obs = steps[i + 1]
                messages.append(
                    ToolMessage(
                        content=obs.tool_output or "",
                        tool_call_id=tool_call_id,
                        name=step.tool_name or "unknown",
                    )
                )
                i += 1
        elif step.step_type == "user" and step.reasoning:
            messages.append(HumanMessage(content=step.reasoning))
        elif step.step_type == "final" and step.reasoning:
            messages.append(AIMessage(content=step.reasoning))
        i += 1
    return messages


class StepRecorder:
    """Records each agent message to agent_steps as the graph streams."""

    def __init__(self, task_id: uuid.UUID, start_step_number: int = 0):
        self.task_id = task_id
        self.step_number = start_step_number
        self._seen_message_count = 0

    async def process_messages(self, messages: list[Any]) -> None:
        new_messages = messages[self._seen_message_count :]
        self._seen_message_count = len(messages)
        for msg in new_messages:
            await self._persist_message(msg)

    async def _persist_message(self, msg: Any) -> None:
        msg_type = getattr(msg, "type", None)
        async with AsyncSessionLocal() as db:
            if msg_type == "ai":
                content = getattr(msg, "content", "") or ""
                if isinstance(content, list):
                    content = str(content)
                tool_calls = getattr(msg, "tool_calls", None) or []
                if tool_calls:
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            name, args = tc.get("name"), tc.get("args", {})
                        else:
                            name, args = getattr(tc, "name", None), getattr(tc, "args", {})
                        self.step_number += 1
                        await steps_repo.create_step(
                            db,
                            task_id=self.task_id,
                            step_number=self.step_number,
                            step_type="tool_call",
                            tool_name=name,
                            tool_input=args,
                        )
                elif content.strip():
                    self.step_number += 1
                    await steps_repo.create_step(
                        db,
                        task_id=self.task_id,
                        step_number=self.step_number,
                        step_type="thought",
                        reasoning=content,
                    )
            elif msg_type == "tool":
                self.step_number += 1
                await steps_repo.create_step(
                    db,
                    task_id=self.task_id,
                    step_number=self.step_number,
                    step_type="observation",
                    tool_name=getattr(msg, "name", None),
                    tool_output=str(getattr(msg, "content", "")),
                )


async def create_task_record(prompt: str) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        task = await tasks_repo.create_task(
            db, user_id=default_user_id(), input_text=prompt, status="running"
        )
        return task.id


async def complete_task_record(task_id: uuid.UUID, final_output: str) -> None:
    async with AsyncSessionLocal() as db:
        await tasks_repo.complete_task(db, task_id, final_output=final_output)


async def fail_task_record(task_id: uuid.UUID, error: str) -> None:
    async with AsyncSessionLocal() as db:
        await tasks_repo.fail_task(db, task_id, error=error)


async def load_continue_messages(task_id: uuid.UUID, new_prompt: str) -> tuple[str, list[BaseMessage], int]:
    """Append a follow-up user message and rebuild history for another agent turn."""
    async with AsyncSessionLocal() as db:
        task = await tasks_repo.get_task_by_id(db, task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.status == "running":
            raise ValueError(f"Task {task_id} is still running")
        steps = await steps_repo.get_steps_for_task(db, task_id)
        next_step = (steps[-1].step_number if steps else 0) + 1
        await steps_repo.create_step(
            db,
            task_id=task_id,
            step_number=next_step,
            step_type="user",
            reasoning=new_prompt,
        )
        await tasks_repo.reset_task_running(db, task_id)
        steps = await steps_repo.get_steps_for_task(db, task_id)
        last_step = steps[-1].step_number if steps else 0
        return task.input, messages_to_langchain(task.input, steps), last_step


async def load_resume_messages(task_id: uuid.UUID) -> tuple[str, list[BaseMessage], int]:
    async with AsyncSessionLocal() as db:
        task = await tasks_repo.get_task_by_id(db, task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.status == "completed":
            raise ValueError(f"Task {task_id} already completed")
        steps = await steps_repo.get_steps_for_task(db, task_id)
        last_step = steps[-1].step_number if steps else 0
        await tasks_repo.reset_task_running(db, task_id)
        return task.input, messages_to_langchain(task.input, steps), last_step
