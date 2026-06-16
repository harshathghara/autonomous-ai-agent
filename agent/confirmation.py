"""Confirmation wrapper for destructive agent tools (CLI or web UI)."""

import asyncio
import json
from collections.abc import Callable

from langchain_core.tools import BaseTool

from agent.errors import retry_hint_for
from agent.web_confirmation import request_confirmation_async, request_confirmation_sync

CONFIRMATION_TOOLS = frozenset({"email_send", "calendar_write", "calendar_delete"})


def _format_preview(tool_name: str, kwargs: dict) -> str:
    try:
        body = json.dumps(kwargs, indent=2, ensure_ascii=False)
    except TypeError:
        body = str(kwargs)
    return f"\n--- Confirm action: {tool_name} ---\n{body}\n"


def _prompt_user_cli(tool_name: str, kwargs: dict) -> bool:
    print(_format_preview(tool_name, kwargs))
    answer = input("Proceed? [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def _cancelled_response(tool_name: str) -> str:
    return json.dumps(
        {
            "status": "cancelled",
            "tool": tool_name,
            "message": f"User declined {tool_name}. Tell the user the action was not performed.",
            "retry_hint": retry_hint_for(tool_name, "cancelled"),
        },
        indent=2,
    )


async def _prompt_user_async(tool_name: str, kwargs: dict) -> bool:
    web_result = await request_confirmation_async(tool_name, kwargs)
    if web_result is not None:
        return web_result
    return await asyncio.to_thread(_prompt_user_cli, tool_name, kwargs)


def _prompt_user(tool_name: str, kwargs: dict) -> bool:
    web_result = request_confirmation_sync(tool_name, kwargs)
    if web_result is not None:
        return web_result
    return _prompt_user_cli(tool_name, kwargs)


def wrap_tool_with_confirmation(tool: BaseTool) -> BaseTool:
    """Return a copy of the tool that asks for confirmation before running."""
    if tool.name not in CONFIRMATION_TOOLS:
        return tool

    original: Callable = tool.func  # type: ignore[assignment]

    def confirmed_func(*args, **kwargs):
        if not _prompt_user(tool.name, kwargs):
            return _cancelled_response(tool.name)
        return original(*args, **kwargs)

    async def confirmed_coro(*args, **kwargs):
        if not await _prompt_user_async(tool.name, kwargs):
            return _cancelled_response(tool.name)
        return await asyncio.to_thread(original, *args, **kwargs)

    return tool.model_copy(update={"func": confirmed_func, "coroutine": confirmed_coro})


def apply_confirmations(tools: list[BaseTool], *, auto_approve: bool) -> list[BaseTool]:
    if auto_approve:
        return tools
    return [wrap_tool_with_confirmation(t) for t in tools]
