"""Tests for tool error formatting and retry hints."""

import json

from agent.errors import enrich_tool_result, format_tool_exception, retry_hint_for


def test_format_tool_exception_includes_retry_hint():
    out = format_tool_exception("calendar_write", ValueError("connection failed"))
    data = json.loads(out)
    assert data["status"] == "error"
    assert data["tool"] == "calendar_write"
    assert "retry_hint" in data


def test_enrich_tool_result_adds_hint_to_error_json():
    raw = json.dumps({"status": "error", "error": "Start time is in the past"})
    out = enrich_tool_result("calendar_write", raw)
    data = json.loads(out)
    assert "past" in data["retry_hint"].lower()


def test_enrich_tool_result_adds_hint_to_cancelled():
    raw = json.dumps({"status": "cancelled", "message": "User declined"})
    out = enrich_tool_result("email_send", raw)
    data = json.loads(out)
    assert "declined" in data["retry_hint"].lower() or "cancelled" in data["retry_hint"].lower()


def test_retry_hint_past_dates():
    hint = retry_hint_for("calendar_write", "Start time 2020-01-01 is in the past")
    assert "past" in hint.lower()
