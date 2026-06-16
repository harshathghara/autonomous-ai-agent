"""Summarize long tasks into agent_memory to preserve context across sessions."""

import uuid

from agent.memory import upsert_memory_sync

_SUMMARY_STEP_THRESHOLD = 8
_LAST_SUMMARY_KEY = "last_task_summary"


def _tool_names_from_messages(messages: list) -> list[str]:
    names: list[str] = []
    for msg in messages:
        if getattr(msg, "type", None) != "ai":
            continue
        for tc in getattr(msg, "tool_calls", None) or []:
            if isinstance(tc, dict):
                name = tc.get("name")
            else:
                name = getattr(tc, "name", None)
            if name:
                names.append(name)
    return names


def maybe_save_task_summary(
    task_id: uuid.UUID,
    prompt: str,
    messages: list,
    step_count: int,
) -> bool:
    """Save a short summary to memory when a task used many steps."""
    if step_count < _SUMMARY_STEP_THRESHOLD:
        return False

    tools_used = _tool_names_from_messages(messages)
    final = ""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai":
            content = getattr(msg, "content", "") or ""
            if isinstance(content, str) and content.strip() and not getattr(msg, "tool_calls", None):
                final = content.strip()
                break

    summary = (
        f"Task ({task_id}): {prompt[:300]}\n"
        f"Tools used ({len(tools_used)}): {', '.join(tools_used) or 'none'}\n"
        f"Outcome: {final[:500] or '(no final answer)'}"
    )
    upsert_memory_sync(_LAST_SUMMARY_KEY, summary, source=str(task_id))
    return True
