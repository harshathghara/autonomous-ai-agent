"""End-to-end workflow tests — multi-tool chains with mocked external APIs."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from agent.graph import build_system_prompt
from agent.memory import format_memories_for_prompt
from agent.tools.calendar import _create_event
from agent.tools.email import _send_email
from agent.tools.web_search import _search


@pytest.fixture(autouse=True)
def utc_calendar_timezone():
    import agent.tools.calendar as calendar_mod

    calendar_mod._cached_tz_name = "UTC"
    with patch("agent.tools.calendar.get_timezone_name", return_value="UTC"):
        yield
    calendar_mod._cached_tz_name = None


def test_conference_workflow_tool_chain(auth_env, groq_api_key):
    """Simulates search → email → calendar for a multi-step research task."""
    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {
        "results": [
            {
                "title": "PyCon US 2026",
                "url": "https://pycon.org",
                "content": "The largest Python conference.",
            },
            {
                "title": "EuroPython 2026",
                "url": "https://europython.eu",
                "content": "Europe's Python conference.",
            },
        ]
    }
    search_out = json.loads(_search("best Python conferences 2026", max_results=3, client=mock_tavily))
    assert search_out["results"]

    summary = "\n".join(f"- {r['title']}: {r['content']}" for r in search_out["results"])

    mock_gmail = MagicMock()
    mock_gmail.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "user@gmail.com"
    }
    mock_gmail.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "msg-1"
    }
    with patch("agent.tools.email._get_gmail_service", return_value=mock_gmail):
        email_out = json.loads(
            _send_email(to="me", subject="Python conferences 2026", body=summary)
        )
    assert email_out["status"] == "sent"

    tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    mock_cal = MagicMock()
    mock_cal.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt-1",
        "summary": "PyCon US 2026",
        "htmlLink": "https://calendar.google.com",
        "start": {"dateTime": f"{tomorrow}T10:00:00+00:00"},
        "end": {"dateTime": f"{tomorrow}T11:00:00+00:00"},
    }
    with patch("agent.tools.calendar._get_calendar_service", return_value=mock_cal):
        cal_out = json.loads(
            _create_event(
                summary="PyCon US 2026",
                start=f"{tomorrow}T10:00:00",
                end=f"{tomorrow}T11:00:00",
                description="Block time to review conference",
            )
        )
    assert cal_out["status"] == "created"


def test_memory_preference_in_system_prompt():
    with patch(
        "agent.memory.list_memories_sync",
        return_value=[{"memory_key": "preferred_meeting_time", "value": "10 am", "source": None}],
    ):
        section = format_memories_for_prompt()
    prompt = build_system_prompt(memory_section=section)
    assert "preferred_meeting_time" in prompt
    assert "10 am" in prompt
    assert "memory_read" in prompt


def test_workflow_uses_preferred_time_for_calendar(auth_env):
    """Calendar event at 10:00 when memory says preferred_meeting_time = 10 am."""
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    mock_cal = MagicMock()
    mock_cal.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt-pref",
        "summary": "Daily standup",
        "htmlLink": "https://calendar.google.com",
        "start": {"dateTime": f"{tomorrow}T10:00:00+00:00"},
        "end": {"dateTime": f"{tomorrow}T11:00:00+00:00"},
    }
    with patch("agent.tools.calendar._get_calendar_service", return_value=mock_cal):
        out = json.loads(
            _create_event(
                summary="Daily standup",
                start=f"{tomorrow}T10:00:00",
                end=f"{tomorrow}T11:00:00",
                description="Uses saved 10 am preference",
            )
        )
    assert out["status"] == "created"
    body = mock_cal.events.return_value.insert.call_args.kwargs["body"]
    assert "10:00:00" in body["start"]["dateTime"]
