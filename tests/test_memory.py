"""Tests for long-term memory (agent_memory)."""

import json
from unittest.mock import patch

import pytest

from agent.memory import (
    format_memories_for_prompt,
    list_memories_sync,
    upsert_memory_sync,
    validate_memory_key,
)
from agent.tools.memory_tools import memory_delete, memory_read, memory_save


def test_validate_memory_key_normalizes():
    assert validate_memory_key("Preferred Meeting Time") == "preferred_meeting_time"


def test_validate_memory_key_rejects_invalid():
    with pytest.raises(ValueError):
        validate_memory_key("123bad")


def test_upsert_and_list_memory(auth_env, monkeypatch):
    fake_rows = []

    def fake_upsert(key, value, *, user_id=None, source=None):
        fake_rows[:] = [{"memory_key": key, "value": value, "source": source}]
        return fake_rows[0]

    with (
        patch("agent.tools.memory_tools.upsert_memory_sync", side_effect=fake_upsert),
        patch("agent.tools.memory_tools.list_memories_sync", return_value=fake_rows),
    ):
            out = memory_save.invoke(
                {
                    "memory_key": "preferred_meeting_time",
                    "value": "10:00 AM",
                    "source": "user stated",
                }
            )
            data = json.loads(out)
            assert data["status"] == "saved"
            assert data["memory_key"] == "preferred_meeting_time"

            read_out = memory_read.invoke({})
            read_data = json.loads(read_out)
            assert read_data["count"] == 1


def test_format_memories_for_prompt_empty():
    with patch("agent.memory.list_memories_sync", return_value=[]):
        assert format_memories_for_prompt() == ""


def test_memory_delete_tool(auth_env):
    with patch("agent.tools.memory_tools.delete_memory_sync") as mock_delete:
        mock_delete.return_value = {"status": "deleted", "memory_key": "email_tone"}
        out = memory_delete.invoke({"memory_key": "email_tone"})
    data = json.loads(out)
    assert data["status"] == "deleted"


def test_format_memories_for_prompt_includes_entries():
    with patch(
        "agent.memory.list_memories_sync",
        return_value=[{"memory_key": "email_tone", "value": "brief", "source": None}],
    ):
        text = format_memories_for_prompt()
        assert "email_tone" in text
        assert "brief" in text
