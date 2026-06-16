"""Builds the LangGraph ReAct agent: Groq LLM + tool binding + system prompt."""

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from agent.tools import get_all_tools
from agent.tools.calendar import get_timezone_name


def _prompt_tz() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(get_timezone_name())
    except Exception:
        return timezone.utc


def build_system_prompt(*, memory_section: str = "") -> str:
    """Include live clock context so relative dates like 'tomorrow' resolve correctly."""
    tz_name = get_timezone_name()
    now = datetime.now(_prompt_tz())
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    return (
        "You are a helpful autonomous assistant with web search, web scraping, Gmail, Google Calendar, and memory tools. "
        "Use web_search to find information, web_scrape for full page text, email_read/email_send for mail, "
        "calendar_read for schedule/meetings, calendar_write to create events, "
        "calendar_delete to remove events (by id from calendar_read or by event title). "
        "Use memory_read to recall saved preferences; use memory_save when the user states a lasting preference "
        "(e.g. preferred meeting time, email tone). "
        f"Current local date/time: {now.strftime('%A, %Y-%m-%d %H:%M')} ({tz_name}). "
        f"When the user says 'tomorrow', use date {tomorrow}. "
        "For calendar_write, pass start/end as local ISO datetimes without timezone suffix "
        "(e.g. 2026-06-05T10:00:00 for 10:00 AM). Never invent past years or random dates. "
        "For email_send: if the user says 'mail me' or does not give a recipient, set to='me'. "
        "Never use example.com or placeholder addresses. Always include a clear subject line. "
        "When scheduling meetings, check memory_read and known preferences (e.g. preferred meeting time) first. "
        "For live sports scores, news, or current events, use web_search with a specific query that includes "
        "today's date from the clock above. Summarize the best match from results in plain text. "
        "If results conflict or look outdated, say that clearly and cite source URLs as plain text (no markdown). "
        "Always end with a plain-text final answer to the user — never stop after tool calls only. "
        "If a tool returns status 'error', read retry_hint, fix inputs, and retry once. "
        "If status is 'cancelled', tell the user nothing was sent or scheduled; do not retry unless they ask."
        f"{memory_section}"
    )


def build_llm() -> ChatGroq:
    return ChatGroq(
        model=os.environ["GROQ_MODEL"],
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0,
        max_tokens=4096,
    )


def build_agent(*, memory_section: str = "", auto_approve: bool = False):
    """Return a compiled LangGraph ReAct agent with web tools."""
    tools = get_all_tools(auto_approve=auto_approve)
    llm = build_llm().bind_tools(tools, tool_choice="auto")
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=build_system_prompt(memory_section=memory_section),
    )
