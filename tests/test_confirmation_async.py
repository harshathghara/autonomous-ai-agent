"""Tests for async confirmation path used by the web UI."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.confirmation import wrap_tool_with_confirmation


@pytest.mark.asyncio
async def test_async_confirmation_uses_web_broker():
    mock_tool = MagicMock()
    mock_tool.name = "calendar_write"
    mock_tool.func.return_value = '{"status": "created"}'
    mock_tool.model_copy.side_effect = lambda update: MagicMock(
        name="calendar_write",
        func=update["func"],
        coroutine=update.get("coroutine"),
    )

    wrapped = wrap_tool_with_confirmation(mock_tool)
    with patch(
        "agent.confirmation.request_confirmation_async",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await wrapped.coroutine(summary="Meet", start="2026-06-09T10:00:00", end="2026-06-09T11:00:00")

    assert json.loads(result)["status"] == "created"
    mock_tool.func.assert_called_once()


@pytest.mark.asyncio
async def test_async_confirmation_declined_skips_tool():
    mock_tool = MagicMock()
    mock_tool.name = "email_send"
    mock_tool.func.return_value = '{"status": "sent"}'
    mock_tool.model_copy.side_effect = lambda update: MagicMock(
        name="email_send",
        func=update["func"],
        coroutine=update.get("coroutine"),
    )

    wrapped = wrap_tool_with_confirmation(mock_tool)
    with patch(
        "agent.confirmation.request_confirmation_async",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await wrapped.coroutine(to="me", subject="Hi", body="Hello")

    data = json.loads(result)
    assert data["status"] == "cancelled"
    mock_tool.func.assert_not_called()
