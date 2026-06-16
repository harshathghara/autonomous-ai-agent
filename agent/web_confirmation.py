"""Web-based confirmation for destructive tools when auto_approve is off."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

PublishFn = Callable[[uuid.UUID, dict[str, Any]], Awaitable[None]]

_confirmation_task_id: ContextVar[uuid.UUID | None] = ContextVar("confirmation_task_id", default=None)


class WebConfirmationBroker:
    def __init__(self, publish: PublishFn) -> None:
        self._publish = publish
        self._pending: dict[str, asyncio.Future[bool]] = {}
        self._outstanding: dict[str, dict[str, Any]] = {}

    async def request(self, task_id: uuid.UUID, tool_name: str, kwargs: dict) -> bool:
        confirmation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[confirmation_id] = future
        event = {
            "type": "confirmation_required",
            "confirmation_id": confirmation_id,
            "tool": tool_name,
            "input": kwargs,
            "task_id": str(task_id),
        }
        self._outstanding[confirmation_id] = event
        await self._publish(task_id, event)
        try:
            return await asyncio.wait_for(future, timeout=300)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending.pop(confirmation_id, None)
            self._outstanding.pop(confirmation_id, None)

    def resolve(self, confirmation_id: str, approved: bool) -> bool:
        future = self._pending.get(confirmation_id)
        if future is None or future.done():
            return False
        future.set_result(approved)
        return True

    def pending_events_for_task(self, task_id: uuid.UUID) -> list[dict[str, Any]]:
        tid = str(task_id)
        return [e for e in self._outstanding.values() if e.get("task_id") == tid]


_broker: WebConfirmationBroker | None = None


def init_web_confirmation_broker(publish: PublishFn) -> WebConfirmationBroker:
    global _broker
    _broker = WebConfirmationBroker(publish)
    return _broker


def get_web_confirmation_broker() -> WebConfirmationBroker | None:
    return _broker


def activate_web_confirmation(task_id: uuid.UUID, loop: asyncio.AbstractEventLoop) -> None:
    del loop  # kept for call-site compatibility
    _confirmation_task_id.set(task_id)


def deactivate_web_confirmation() -> None:
    _confirmation_task_id.set(None)


async def request_confirmation_async(tool_name: str, kwargs: dict) -> bool | None:
    """Await web UI approval on the running event loop, or None for CLI fallback."""
    task_id = _confirmation_task_id.get()
    broker = get_web_confirmation_broker()
    if task_id is None or broker is None:
        return None
    return await broker.request(task_id, tool_name, kwargs)


def request_confirmation_sync(tool_name: str, kwargs: dict) -> bool | None:
    """Sync fallback when tools run outside the async event loop (tests / sync invoke)."""
    task_id = _confirmation_task_id.get()
    broker = get_web_confirmation_broker()
    if task_id is None or broker is None:
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    future = asyncio.run_coroutine_threadsafe(broker.request(task_id, tool_name, kwargs), loop)
    try:
        return future.result(timeout=300)
    except (asyncio.TimeoutError, TimeoutError):
        return False
