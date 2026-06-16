"""Google Calendar tools — calendar_read, calendar_write, and calendar_delete."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from auth.token_store import load_credentials_sync

_cached_tz_name: str | None = None


def _fetch_calendar_timezone(service) -> str:
    cal = service.calendarList().get(calendarId="primary").execute()
    return cal.get("timeZone") or "UTC"


def get_timezone_name() -> str:
    """Prefer the user's Google Calendar timezone; fall back to USER_TIMEZONE env."""
    global _cached_tz_name
    if _cached_tz_name:
        return _cached_tz_name
    try:
        _cached_tz_name = _fetch_calendar_timezone(_get_calendar_service())
    except Exception:
        _cached_tz_name = os.getenv("USER_TIMEZONE", "UTC") or "UTC"
    return _cached_tz_name


def _user_tz() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(get_timezone_name())
    except Exception:
        return timezone.utc


class CalendarReadInput(BaseModel):
    # Groq sends numeric tool args as strings — schema uses str, we coerce in the tool.
    days_ahead: str = Field("7", description="How many days ahead to list events (1-30)")
    max_results: str = Field("20", description="Maximum number of events to return (1-50)")


class CalendarDeleteInput(BaseModel):
    event_id: str = Field(
        "",
        description="Google Calendar event ID from calendar_read — preferred when available",
    )
    summary: str = Field(
        "",
        description="Event title to find and delete (case-insensitive partial match)",
    )
    days_back: str = Field(
        "365",
        description="Days into the past to search when matching by summary (1-3650)",
    )
    days_ahead: str = Field(
        "30",
        description="Days into the future to search when matching by summary (1-365)",
    )


class CalendarWriteInput(BaseModel):
    summary: str = Field(..., description="Event title")
    start: str = Field(
        ...,
        description=(
            "Start time as local ISO datetime (no Z suffix), e.g. 2026-06-05T10:00:00. "
            "Use the current date from the system prompt — 'tomorrow' means today+1 day."
        ),
    )
    end: str = Field(
        ...,
        description="End time as local ISO datetime (no Z suffix), e.g. 2026-06-05T11:00:00",
    )
    description: str = Field("", description="Optional event description")


def _get_calendar_service():
    creds = load_credentials_sync()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_user_tz())
    return dt.isoformat()


def _read_events(days_ahead: int, max_results: int) -> str:
    service = _get_calendar_service()
    now = datetime.now(_user_tz())
    time_min = _to_rfc3339(now)
    time_max = _to_rfc3339(now + timedelta(days=days_ahead))

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = []
    for item in events_result.get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})
        events.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary", "(no title)"),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "location": item.get("location"),
                "description": (item.get("description") or "")[:200],
            }
        )
    return json.dumps(
        {"days_ahead": days_ahead, "count": len(events), "events": events},
        indent=2,
    )


def _parse_local_datetime(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_user_tz())
    return dt


def _validate_event_times(start: str, end: str) -> tuple[str, str] | dict:
    now = datetime.now(_user_tz())
    try:
        start_dt = _parse_local_datetime(start)
        end_dt = _parse_local_datetime(end)
    except ValueError:
        return {
            "status": "error",
            "error": f"Invalid datetime format. Use local ISO like {now.strftime('%Y-%m-%dT%H:%M:%S')}.",
            "start": start,
            "end": end,
            "current_time": now.isoformat(),
        }
    if start_dt < now - timedelta(minutes=1):
        return {
            "status": "error",
            "error": (
                f"Start time {start} is in the past. Current time is {now.strftime('%Y-%m-%d %H:%M')} "
                f"({_user_tz()}). Recompute using today's date from the system prompt."
            ),
            "start": start,
            "end": end,
            "current_time": now.isoformat(),
        }
    if end_dt <= start_dt:
        return {
            "status": "error",
            "error": "End time must be after start time.",
            "start": start,
            "end": end,
            "current_time": now.isoformat(),
        }
    start_dt = _parse_local_datetime(start)
    end_dt = _parse_local_datetime(end)
    return start_dt.isoformat(), end_dt.isoformat()


def _list_events_in_range(service, days_back: int, days_ahead: int, max_results: int = 50) -> list[dict]:
    now = datetime.now(_user_tz())
    time_min = _to_rfc3339(now - timedelta(days=days_back))
    time_max = _to_rfc3339(now + timedelta(days=days_ahead))
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


def _event_summary(item: dict) -> str:
    return item.get("summary") or "(no title)"


def _delete_event_by_id(service, event_id: str) -> dict:
    existing = service.events().get(calendarId="primary", eventId=event_id).execute()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    start = existing.get("start", {})
    end = existing.get("end", {})
    return {
        "id": event_id,
        "summary": _event_summary(existing),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
    }


def _delete_events(
    event_id: str,
    summary: str,
    days_back: int,
    days_ahead: int,
) -> str:
    event_id = event_id.strip()
    summary = summary.strip()
    if not event_id and not summary:
        return json.dumps(
            {
                "status": "error",
                "error": "Provide event_id (from calendar_read) or summary (event title) to delete.",
            },
            indent=2,
        )

    service = _get_calendar_service()

    if event_id:
        try:
            deleted = _delete_event_by_id(service, event_id)
        except Exception as exc:
            return json.dumps(
                {"status": "error", "error": f"Failed to delete event {event_id}: {exc}"},
                indent=2,
            )
        return json.dumps({"status": "deleted", "count": 1, "deleted": [deleted]}, indent=2)

    needle = summary.lower()
    matches = [
        item
        for item in _list_events_in_range(service, days_back, days_ahead, max_results=100)
        if needle in _event_summary(item).lower()
    ]
    if not matches:
        return json.dumps(
            {
                "status": "error",
                "error": f"No events found matching summary '{summary}'. Run calendar_read first.",
                "summary": summary,
                "days_back": days_back,
                "days_ahead": days_ahead,
            },
            indent=2,
        )

    deleted = []
    errors = []
    for item in matches:
        evt_id = item["id"]
        try:
            deleted.append(_delete_event_by_id(service, evt_id))
        except Exception as exc:
            errors.append({"id": evt_id, "summary": _event_summary(item), "error": str(exc)})

    result: dict = {"status": "deleted", "count": len(deleted), "deleted": deleted}
    if errors:
        result["errors"] = errors
    if not deleted:
        result["status"] = "error"
        result["error"] = "Matched events but deletion failed for all of them."
    return json.dumps(result, indent=2)


def _create_event(summary: str, start: str, end: str, description: str) -> str:
    validated = _validate_event_times(start, end)
    if isinstance(validated, dict):
        return json.dumps(validated, indent=2)

    start, end = validated
    service = _get_calendar_service()
    tz_name = get_timezone_name()
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start, "timeZone": tz_name},
        "end": {"dateTime": end, "timeZone": tz_name},
    }
    created = service.events().insert(calendarId="primary", body=body).execute()
    start_info = created.get("start", {})
    end_info = created.get("end", {})
    return json.dumps(
        {
            "status": "created",
            "id": created.get("id"),
            "summary": created.get("summary"),
            "htmlLink": created.get("htmlLink"),
            "timezone": tz_name,
            "start": start_info,
            "end": end_info,
            "local_start": start_info.get("dateTime") or start_info.get("date"),
            "local_end": end_info.get("dateTime") or end_info.get("date"),
        },
        indent=2,
    )


@tool(args_schema=CalendarReadInput)
def calendar_read(
    days_ahead: Annotated[str, "How many days ahead to list events"] = "7",
    max_results: Annotated[str, "Maximum events to return"] = "20",
) -> str:
    """List upcoming Google Calendar events for the user. Use for meetings, schedule, availability."""
    return _read_events(days_ahead=int(days_ahead), max_results=int(max_results))


@tool(args_schema=CalendarDeleteInput)
def calendar_delete(
    event_id: Annotated[str, "Event ID from calendar_read"] = "",
    summary: Annotated[str, "Event title to find and delete"] = "",
    days_back: Annotated[str, "Days back to search when matching by title"] = "365",
    days_ahead: Annotated[str, "Days ahead to search when matching by title"] = "30",
) -> str:
    """Delete calendar event(s) by ID or by matching event title. Use calendar_read first to get IDs."""
    return _delete_events(
        event_id=event_id,
        summary=summary,
        days_back=int(days_back),
        days_ahead=int(days_ahead),
    )


@tool(args_schema=CalendarWriteInput)
def calendar_write(
    summary: Annotated[str, "Event title"],
    start: Annotated[str, "Start time ISO format"],
    end: Annotated[str, "End time ISO format"],
    description: Annotated[str, "Optional event description"] = "",
) -> str:
    """Create a new event on the user's Google Calendar."""
    return _create_event(summary=summary, start=start, end=end, description=description)
