"""Tests for shared agent runner event extraction."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.runner import extract_final_content, messages_to_events


def test_messages_to_events():
    messages = [
        HumanMessage(content="hi"),
        AIMessage(content="thinking"),
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "x"}, "id": "1"}]),
        ToolMessage(content='{"results":[]}', tool_call_id="1", name="web_search"),
        AIMessage(content="done"),
    ]
    events = messages_to_events(messages)
    types = [e["type"] for e in events]
    assert types == ["thought", "tool_call", "tool_result", "thought"]


def test_extract_final_content():
    messages = [
        HumanMessage(content="q"),
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {}, "id": "1"}]),
        AIMessage(content="Final answer here"),
    ]
    assert extract_final_content(messages) == "Final answer here"
