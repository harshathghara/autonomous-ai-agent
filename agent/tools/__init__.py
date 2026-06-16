"""Registers all LangChain tools exposed to the agent (search, scrape, email, memory)."""

from langchain_core.tools import BaseTool

from agent.confirmation import apply_confirmations
from agent.errors import wrap_tool_safe
from agent.tools.calendar import calendar_delete, calendar_read, calendar_write
from agent.tools.email import email_read, email_send
from agent.tools.memory_tools import memory_delete, memory_read, memory_save
from agent.tools.web_scrape import web_scrape
from agent.tools.web_search import web_search


def get_all_tools(*, auto_approve: bool = False) -> list[BaseTool]:
    tools = [
        web_search,
        web_scrape,
        email_read,
        email_send,
        calendar_read,
        calendar_write,
        calendar_delete,
        memory_read,
        memory_save,
        memory_delete,
    ]
    tools = [wrap_tool_safe(t) for t in tools]
    return apply_confirmations(tools, auto_approve=auto_approve)
