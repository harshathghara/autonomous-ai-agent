"""Tests for Google Calendar tools (mocked API)."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import agent.tools.calendar as calendar_mod
from agent.tools.calendar import _create_event, _delete_events, _read_events


@pytest.fixture(autouse=True)
def utc_calendar_timezone():
    calendar_mod._cached_tz_name = "UTC"
    with patch("agent.tools.calendar.get_timezone_name", return_value="UTC"):
        yield
    calendar_mod._cached_tz_name = None


def test_read_events_returns_list(auth_env):
    mock_service = MagicMock()
    mock_service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt-1",
                "summary": "Team standup",
                "start": {"dateTime": "2026-06-10T10:00:00+00:00"},
                "end": {"dateTime": "2026-06-10T10:30:00+00:00"},
            }
        ]
    }

    with patch("agent.tools.calendar._get_calendar_service", return_value=mock_service):
        out = _read_events(days_ahead=7, max_results=10)

    data = json.loads(out)
    assert data["count"] == 1
    assert data["events"][0]["summary"] == "Team standup"


def test_create_event_returns_id(auth_env):
    future = (datetime.now(timezone.utc) + timedelta(days=7)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    end = future + timedelta(hours=1)
    start_iso = future.strftime("%Y-%m-%dT%H:%M:%S")
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%S")

    mock_service = MagicMock()
    mock_service.events.return_value.insert.return_value.execute.return_value = {
        "id": "new-evt",
        "summary": "Focus time",
        "htmlLink": "https://calendar.google.com/event?id=new-evt",
        "start": {"dateTime": f"{start_iso}+00:00"},
        "end": {"dateTime": f"{end_iso}+00:00"},
    }

    with patch("agent.tools.calendar._get_calendar_service", return_value=mock_service):
        out = _create_event(
            summary="Focus time",
            start=start_iso,
            end=end_iso,
            description="",
        )

    data = json.loads(out)
    assert data["status"] == "created"
    assert data["id"] == "new-evt"
    assert data["timezone"] == "UTC"
    insert_body = mock_service.events.return_value.insert.call_args.kwargs["body"]
    assert insert_body["start"]["timeZone"] == "UTC"


def test_delete_event_by_id(auth_env):
    mock_service = MagicMock()
    mock_service.events.return_value.get.return_value.execute.return_value = {
        "id": "evt-99",
        "summary": "daily standup",
        "start": {"dateTime": "2024-09-17T10:00:00+00:00"},
        "end": {"dateTime": "2024-09-17T11:00:00+00:00"},
    }
    mock_service.events.return_value.delete.return_value.execute.return_value = None

    with patch("agent.tools.calendar._get_calendar_service", return_value=mock_service):
        out = _delete_events(event_id="evt-99", summary="", days_back=365, days_ahead=30)

    data = json.loads(out)
    assert data["status"] == "deleted"
    assert data["count"] == 1
    assert data["deleted"][0]["summary"] == "daily standup"
    mock_service.events.return_value.delete.assert_called_once()


def test_delete_events_by_summary(auth_env):
    mock_service = MagicMock()
    mock_service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt-a",
                "summary": "daily standup",
                "start": {"dateTime": "2024-09-17T10:00:00+00:00"},
                "end": {"dateTime": "2024-09-17T11:00:00+00:00"},
            }
        ]
    }
    mock_service.events.return_value.get.return_value.execute.return_value = {
        "id": "evt-a",
        "summary": "daily standup",
        "start": {"dateTime": "2024-09-17T10:00:00+00:00"},
        "end": {"dateTime": "2024-09-17T11:00:00+00:00"},
    }
    mock_service.events.return_value.delete.return_value.execute.return_value = None

    with patch("agent.tools.calendar._get_calendar_service", return_value=mock_service):
        out = _delete_events(event_id="", summary="standup", days_back=365, days_ahead=30)

    data = json.loads(out)
    assert data["status"] == "deleted"
    assert data["count"] == 1


def test_delete_events_requires_id_or_summary(auth_env):
    out = _delete_events(event_id="", summary="", days_back=30, days_ahead=30)
    data = json.loads(out)
    assert data["status"] == "error"


def test_create_event_rejects_past_date(auth_env):
    out = _create_event(
        summary="Old meeting",
        start="2020-01-01T10:00:00",
        end="2020-01-01T11:00:00",
        description="",
    )
    data = json.loads(out)
    assert data["status"] == "error"
    assert "past" in data["error"].lower()
