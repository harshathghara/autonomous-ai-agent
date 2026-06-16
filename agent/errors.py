"""Tool error formatting and safe wrappers so the agent can recover gracefully."""

import json
from collections.abc import Callable

from langchain_core.tools import BaseTool

_RETRY_HINTS: dict[str, str] = {
    "calendar_write": "Check start/end dates against the current date in the system prompt. Use local ISO times.",
    "calendar_delete": "Run calendar_read first to get the exact event id or summary spelling.",
    "calendar_read": "Try a larger days_ahead value or verify Google Calendar OAuth is connected.",
    "email_send": "Use to='me' when the user did not specify a recipient. Never use example.com.",
    "email_read": "Try a simpler Gmail query or fewer max_results.",
    "web_search": "Rephrase the query with more specific keywords.",
    "web_scrape": "Use a full https URL from web_search results.",
    "memory_save": "memory_key must be snake_case starting with a letter.",
    "memory_delete": "Run memory_read first to see available keys.",
}


def retry_hint_for(tool_name: str, error: str = "") -> str:
    base = _RETRY_HINTS.get(tool_name, "Read the error, adjust inputs, and retry once.")
    if "past" in error.lower():
        return "The date is in the past. Recompute using tomorrow's date from the system prompt."
    if "cancelled" in error.lower():
        return "The user declined this action. Explain what was not done; do not retry unless they ask."
    return base


def format_tool_exception(tool_name: str, exc: Exception) -> str:
    message = str(exc)
    return json.dumps(
        {
            "status": "error",
            "tool": tool_name,
            "error": message,
            "retry_hint": retry_hint_for(tool_name, message),
        },
        indent=2,
    )


def enrich_tool_result(tool_name: str, result: str) -> str:
    """Add retry_hint to JSON tool results that are errors or cancellations."""
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return result
    if not isinstance(data, dict):
        return result
    status = data.get("status")
    if status in ("error", "cancelled") and "retry_hint" not in data:
        error_text = data.get("error") or data.get("message") or ""
        if status == "cancelled":
            error_text = f"cancelled {error_text}"
        data["retry_hint"] = retry_hint_for(tool_name, str(error_text))
        return json.dumps(data, indent=2)
    return result


def wrap_tool_safe(tool: BaseTool) -> BaseTool:
    original: Callable = tool.func  # type: ignore[assignment]

    def safe_func(*args, **kwargs):
        try:
            result = original(*args, **kwargs)
            return enrich_tool_result(tool.name, result if isinstance(result, str) else str(result))
        except Exception as exc:
            return format_tool_exception(tool.name, exc)

    return tool.model_copy(update={"func": safe_func})
