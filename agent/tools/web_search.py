"""Web search tool — queries Tavily API and returns JSON results for the agent."""

import json
import os
from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from tavily import TavilyClient


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query for the web")
    max_results: int = Field(5, ge=1, le=10, description="Number of results to return")


def _search(query: str, max_results: int, client: TavilyClient | None = None) -> str:
    tavily = client or TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = tavily.search(query=query, max_results=max_results)
    results = [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "content": item.get("content"),
        }
        for item in response.get("results", [])
    ]
    return json.dumps({"query": query, "results": results}, indent=2)


@tool(args_schema=WebSearchInput)
def web_search(
    query: Annotated[str, "Search query for the web"],
    max_results: Annotated[int, "Number of results (1-10)"] = 5,
) -> str:
    """Search the web for current information using Tavily. Use for research, news, and facts."""
    return _search(query=query, max_results=max_results)
