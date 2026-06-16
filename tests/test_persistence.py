"""Tests for step persistence and message reconstruction."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.persistence import messages_to_langchain


def test_messages_to_langchain_rebuilds_tool_loop():
    steps = [
        SimpleNamespace(
            step_number=1,
            step_type="tool_call",
            tool_name="web_search",
            tool_input={"query": "test"},
            reasoning=None,
            tool_output=None,
        ),
        SimpleNamespace(
            step_number=2,
            step_type="observation",
            tool_name="web_search",
            tool_input=None,
            reasoning=None,
            tool_output='{"results": []}',
        ),
        SimpleNamespace(
            step_number=3,
            step_type="thought",
            tool_name=None,
            tool_input=None,
            reasoning="Summarizing results.",
            tool_output=None,
        ),
    ]
    messages = messages_to_langchain("search test", steps)
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "search test"
    assert isinstance(messages[1], AIMessage)
    assert messages[1].tool_calls[0]["name"] == "web_search"
    assert isinstance(messages[2], ToolMessage)
    assert isinstance(messages[3], AIMessage)
    assert messages[3].content == "Summarizing results."


def test_messages_to_langchain_includes_follow_up_user_turn():
    steps = [
        SimpleNamespace(
            step_number=1,
            step_type="thought",
            tool_name=None,
            tool_input=None,
            reasoning="First answer.",
            tool_output=None,
        ),
        SimpleNamespace(
            step_number=2,
            step_type="user",
            tool_name=None,
            tool_input=None,
            reasoning="Follow-up question?",
            tool_output=None,
        ),
    ]
    messages = messages_to_langchain("hello", steps)
    assert messages[0].content == "hello"
    assert messages[1].content == "First answer."
    assert isinstance(messages[2], HumanMessage)
    assert messages[2].content == "Follow-up question?"
