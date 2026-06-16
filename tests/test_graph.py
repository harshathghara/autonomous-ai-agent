"""Tests that the agent graph compiles and all tools are registered."""

from unittest.mock import patch

from agent.tools import get_all_tools


def test_get_all_tools_registers_web_tools():
    tools = get_all_tools()
    names = {t.name for t in tools}
    assert names == {
        "web_search",
        "web_scrape",
        "email_read",
        "email_send",
        "calendar_read",
        "calendar_write",
        "calendar_delete",
        "memory_read",
        "memory_save",
        "memory_delete",
    }


def test_build_agent_compiles(groq_api_key):
    with (
        patch("agent.graph.get_timezone_name", return_value="UTC"),
        patch("agent.graph.ChatGroq") as mock_llm,
    ):
        mock_llm.return_value.bind_tools.return_value = mock_llm.return_value
        from agent.graph import build_agent

        graph = build_agent()
        assert graph is not None
