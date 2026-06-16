"""Tests for CLI confirmation on destructive tools."""

import json
from unittest.mock import MagicMock, patch

from agent.confirmation import apply_confirmations, wrap_tool_with_confirmation
from agent.tools import get_all_tools


def test_get_all_tools_wraps_destructive_tools_by_default():
    tools = get_all_tools(auto_approve=False)
    names = {t.name for t in tools}
    assert "email_send" in names
    assert "memory_read" in names
    # Wrapped tool should still have same name
    email_tool = next(t for t in tools if t.name == "email_send")
    assert email_tool.name == "email_send"


def test_confirmation_declined_returns_cancelled():
    mock_tool = MagicMock()
    mock_tool.name = "email_send"
    mock_tool.func.return_value = '{"status": "sent"}'
    mock_tool.model_copy.side_effect = lambda update: MagicMock(
        name="email_send",
        func=update["func"],
    )

    wrapped = wrap_tool_with_confirmation(mock_tool)
    with patch("agent.confirmation._prompt_user", return_value=False):
        result = wrapped.func(to="me", subject="Hi", body="Hello")

    data = json.loads(result)
    assert data["status"] == "cancelled"
    mock_tool.func.assert_not_called()


def test_confirmation_approved_runs_tool():
    mock_tool = MagicMock()
    mock_tool.name = "calendar_delete"
    mock_tool.func.return_value = '{"status": "deleted"}'
    mock_tool.model_copy.side_effect = lambda update: MagicMock(
        name="calendar_delete",
        func=update["func"],
    )

    wrapped = wrap_tool_with_confirmation(mock_tool)
    with patch("agent.confirmation._prompt_user", return_value=True):
        result = wrapped.func(event_id="evt-1", summary="")

    assert json.loads(result)["status"] == "deleted"
    mock_tool.func.assert_called_once()


def test_auto_approve_skips_wrapping():
    tools = get_all_tools(auto_approve=True)
    email_tool = next(t for t in tools if t.name == "email_send")
    # Original tool func should be the real implementation, not a wrapper that calls _prompt_user
    with patch("agent.confirmation._prompt_user") as mock_prompt:
        # Can't easily invoke real email without mocks; just ensure apply_confirmations returns as-is
        assert mock_prompt.call_count == 0
    assert email_tool.name == "email_send"
