"""Tests for web_search and web_scrape tools (mocked external APIs)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.tools.web_scrape import scrape_url
from agent.tools.web_search import _search


def test_web_search_returns_results(tavily_api_key):
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "title": "LangGraph",
                "url": "https://example.com/langgraph",
                "content": "Stateful agent graphs.",
            }
        ]
    }
    out = _search("LangGraph tutorials", max_results=3, client=mock_client)
    data = json.loads(out)
    assert data["query"] == "LangGraph tutorials"
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "LangGraph"
    mock_client.search.assert_called_once_with(query="LangGraph tutorials", max_results=3)


def test_web_scrape_extracts_text(tavily_api_key):
    fake_html = """
    <html><head><style>body{}</style></head>
    <body><script>ignore()</script><p>Hello world from page.</p></body></html>
    """
    mock_page = MagicMock()
    mock_page.content.return_value = fake_html

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_chromium = MagicMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)

    with patch("agent.tools.web_scrape.sync_playwright", return_value=mock_pw):
        text = scrape_url("https://example.com", max_chars=5000)

    assert "Hello world from page" in text
    assert "ignore()" not in text
