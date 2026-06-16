"""Memory tools — memory_read and memory_save for long-term user preferences."""

import json
from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agent.memory import delete_memory_sync, list_memories_sync, upsert_memory_sync, validate_memory_key


class MemoryDeleteInput(BaseModel):
    memory_key: str = Field(..., description="Snake_case key to delete, from memory_read")


class MemorySaveInput(BaseModel):
    memory_key: str = Field(
        ...,
        description="Snake_case key, e.g. preferred_meeting_time, email_tone",
    )
    value: str = Field(..., description="The preference or fact to remember")
    source: str = Field("", description="Optional note about where this came from")


@tool
def memory_read() -> str:
    """List all saved user preferences and facts. Call before scheduling or emailing when preferences may apply."""
    memories = list_memories_sync()
    return json.dumps({"count": len(memories), "memories": memories}, indent=2)


@tool(args_schema=MemorySaveInput)
def memory_save(
    memory_key: Annotated[str, "Snake_case key for this preference"],
    value: Annotated[str, "Preference or fact to remember"],
    source: Annotated[str, "Optional source note"] = "",
) -> str:
    """Save a lasting user preference or fact for future sessions. Use when the user states how they like things done."""
    try:
        key = validate_memory_key(memory_key)
        saved = upsert_memory_sync(key, value, source=source or None)
    except ValueError as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)
    return json.dumps({"status": "saved", **saved}, indent=2)


@tool(args_schema=MemoryDeleteInput)
def memory_delete(
    memory_key: Annotated[str, "Snake_case key to remove"],
) -> str:
    """Delete a saved user preference by key. Use memory_read first to list keys."""
    try:
        key = validate_memory_key(memory_key)
        result = delete_memory_sync(key)
    except ValueError as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)
    return json.dumps(result, indent=2)
