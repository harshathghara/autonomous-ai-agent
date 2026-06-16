"""Shared agent runner for CLI and FastAPI — streams events while executing tasks."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable

from agent.graph import build_agent
from agent.llm_errors import (
    format_llm_error,
    is_retryable_llm_error,
    normalize_tool_args,
    retry_delay_seconds,
)
from agent.memory import format_memories_for_prompt
from agent.persistence import (
    StepRecorder,
    complete_task_record,
    create_task_record,
    fail_task_record,
    load_continue_messages,
    load_resume_messages,
)
from agent.summarize import maybe_save_task_summary

EventCallback = Callable[[dict], Awaitable[None] | None]


def extract_final_content(messages: list) -> str:
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content and getattr(msg, "type", None) == "ai":
            return content if isinstance(content, str) else str(content)
    last = messages[-1]
    return getattr(last, "content", str(last))


def messages_to_events(messages: list, start_index: int = 0) -> list[dict]:
    """Convert new LangChain messages to JSON events for the UI."""
    events: list[dict] = []
    for msg in messages[start_index:]:
        msg_type = getattr(msg, "type", None)
        if msg_type == "human":
            continue
        if msg_type == "ai":
            content = getattr(msg, "content", "") or ""
            if isinstance(content, list):
                content = str(content)
            if content.strip():
                events.append({"type": "thought", "content": content})
            for tc in getattr(msg, "tool_calls", None) or []:
                if isinstance(tc, dict):
                    name, args = tc.get("name", "?"), tc.get("args", {})
                else:
                    name, args = getattr(tc, "name", "?"), getattr(tc, "args", {})
                events.append(
                    {"type": "tool_call", "name": name, "input": normalize_tool_args(args)}
                )
        elif msg_type == "tool":
            events.append(
                {
                    "type": "tool_result",
                    "name": getattr(msg, "name", "?"),
                    "content": str(getattr(msg, "content", "")),
                }
            )
    return events


async def _emit_events(events: list[dict], on_event: EventCallback | None) -> None:
    if not on_event:
        return
    for event in events:
        result = on_event(event)
        if result is not None:
            await result


async def run_agent_task(
    prompt: str,
    *,
    task_id: uuid.UUID | None = None,
    resume: bool = False,
    continue_chat: bool = False,
    auto_approve: bool = False,
    on_event: EventCallback | None = None,
) -> tuple[str, list, uuid.UUID]:
    memory_section = format_memories_for_prompt()
    agent = build_agent(memory_section=memory_section, auto_approve=auto_approve)
    recorder: StepRecorder | None = None
    task_input = prompt
    seen_events = 0

    if continue_chat:
        if task_id is None:
            raise ValueError("continue_chat requires task_id")
        task_input, seed_messages, last_step = await load_continue_messages(task_id, prompt)
        input_state = {"messages": seed_messages}
        recorder = StepRecorder(task_id, start_step_number=last_step)
        recorder._seen_message_count = len(seed_messages)
        seen_events = len(seed_messages)
    elif resume:
        if task_id is None:
            raise ValueError("resume requires task_id")
        task_input, seed_messages, last_step = await load_resume_messages(task_id)
        input_state = {"messages": seed_messages}
        recorder = StepRecorder(task_id, start_step_number=last_step)
        recorder._seen_message_count = len(seed_messages)
        seen_events = len(seed_messages)
        await _emit_events(
            [{"type": "status", "content": f"Resuming task from step {last_step}"}],
            on_event,
        )
    else:
        if task_id is None:
            task_id = await create_task_record(prompt)
        recorder = StepRecorder(task_id)
        input_state = {"messages": [("user", prompt)]}
        await _emit_events(
            [{"type": "task_started", "task_id": str(task_id), "input": prompt}],
            on_event,
        )

    messages: list = []
    llm_retries = 0
    max_llm_retries = 2
    while True:
        try:
            async for chunk in agent.astream(
                input_state,
                config={"recursion_limit": 25},
                stream_mode="values",
            ):
                messages = chunk["messages"]
                await recorder.process_messages(messages)
                new_events = messages_to_events(messages, seen_events)
                seen_events = len(messages)
                await _emit_events(new_events, on_event)
            break
        except Exception as exc:
            if llm_retries < max_llm_retries and is_retryable_llm_error(exc) and messages:
                llm_retries += 1
                input_state = {"messages": messages}
                seen_events = len(messages)
                delay = retry_delay_seconds(exc, llm_retries)
                if delay > 0:
                    await _emit_events(
                        [
                            {
                                "type": "thought",
                                "content": f"Rate limited — retrying in {int(delay)}s…",
                            }
                        ],
                        on_event,
                    )
                    await asyncio.sleep(delay)
                else:
                    await _emit_events(
                        [
                            {
                                "type": "thought",
                                "content": "Retrying after a temporary model formatting error…",
                            }
                        ],
                        on_event,
                    )
                continue
            friendly = format_llm_error(exc)
            await fail_task_record(task_id, friendly)
            await _emit_events([{"type": "error", "message": friendly}], on_event)
            raise

    answer = extract_final_content(messages)
    maybe_save_task_summary(task_id, task_input, messages, recorder.step_number)
    await complete_task_record(task_id, answer)
    await _emit_events(
        [{"type": "final", "content": answer, "task_id": str(task_id)}],
        on_event,
    )
    return answer, messages, task_id
