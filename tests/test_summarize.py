"""Tests for long-task summarization into memory."""

import uuid
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.summarize import maybe_save_task_summary


def test_maybe_save_task_summary_skips_short_tasks():
    with patch("agent.summarize.upsert_memory_sync") as mock_upsert:
        saved = maybe_save_task_summary(
            uuid.uuid4(),
            "short task",
            [HumanMessage(content="hi"), AIMessage(content="done")],
            step_count=3,
        )
    assert saved is False
    mock_upsert.assert_not_called()


def test_maybe_save_task_summary_stores_long_tasks():
    task_id = uuid.uuid4()
    messages = [
        HumanMessage(content="big task"),
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {}, "id": "1"}]),
        AIMessage(content="Finished research and emailed summary."),
    ]
    with patch("agent.summarize.upsert_memory_sync") as mock_upsert:
        saved = maybe_save_task_summary(task_id, "Find conferences and email me", messages, step_count=10)
    assert saved is True
    mock_upsert.assert_called_once()
    key = mock_upsert.call_args[0][0]
    value = mock_upsert.call_args[0][1]
    assert key == "last_task_summary"
    assert "web_search" in value
