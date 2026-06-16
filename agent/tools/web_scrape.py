"""Web scrape tool — fetches a URL with Playwright and returns cleaned plain text."""

from typing import Annotated

from bs4 import BeautifulSoup
from langchain_core.tools import tool
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field, HttpUrl


class WebScrapeInput(BaseModel):
    url: HttpUrl = Field(..., description="URL to fetch and extract text from")
    max_chars: int = Field(8000, ge=500, le=20000, description="Max characters of extracted text")


def _extract_text(html: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ", strip=True).split())
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text


def scrape_url(url: str, max_chars: int = 8000) -> str:
    """Fetch a page with Playwright (sync API — safe inside LangGraph's async executor)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
        finally:
            browser.close()
    return _extract_text(html, max_chars)


@tool(args_schema=WebScrapeInput)
def web_scrape(
    url: Annotated[str, "URL to fetch and extract text from"],
    max_chars: Annotated[int, "Max characters of extracted text"] = 8000,
) -> str:
    """Fetch a web page with Playwright and return cleaned plain text. Use after web_search when you need page detail."""
    return scrape_url(url=str(url), max_chars=max_chars)
