# Week 1 — Foundation, Groq + Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a LangGraph ReAct agent on Groq (`llama-3.3-70b-versatile`) with Tavily web search and Playwright scraping tools, verified end-to-end via CLI and unit tests.

**Architecture:** Thin `agent/` package: tools register via `get_all_tools()`, graph built with `create_react_agent` from LangGraph prebuilt. Week 1 has no PostgreSQL or FastAPI — a `run_agent.py` CLI invokes the graph for manual smoke tests. Tool I/O validated with Pydantic before execution.

**Tech Stack:** Python 3.11+, LangGraph, langchain-groq, Tavily API, Playwright, pytest, python-dotenv

---

## Week 1 scope (in / out)

| In scope | Deferred to Week 2+ |
|---|---|
| LangGraph + Groq ReAct loop | PostgreSQL, Alembic |
| Tavily `web_search` tool | Gmail / Calendar |
| Playwright `web_scrape` tool | FastAPI, WebSockets |
| Tool unit tests (mocked) | OAuth, step persistence |
| CLI smoke test | React frontend |

**Success criteria:** `pytest` passes; `python run_agent.py "Search for top Python frameworks in 2026 and summarize"` completes with a final answer referencing search results.

---

## File map

| Path | Responsibility |
|---|---|
| `agent/graph.py` | Build Groq LLM + `create_react_agent` |
| `agent/tools/__init__.py` | `get_all_tools()` registry |
| `agent/tools/web_search.py` | Tavily search LangChain tool |
| `agent/tools/web_scrape.py` | Playwright fetch + BeautifulSoup extract |
| `run_agent.py` | CLI entry for smoke tests |
| `tests/conftest.py` | Fixtures, env loading |
| `tests/test_tools.py` | Mocked Tavily + Playwright tests |
| `tests/test_graph.py` | Graph builds; optional integration mark |
| `requirements.txt` | Pinned deps |
| `.env.example` | Key names only |
| `.gitignore` | Exclude `.env`, `__pycache__`, `.pytest_cache` |

---

### Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `agent/__init__.py`, `README.md`

- [ ] **Step 1:** Create `requirements.txt` with core deps
- [ ] **Step 2:** Create `.gitignore` (`.env`, venv, pytest cache)
- [ ] **Step 3:** Create `.env.example` documenting `GROQ_API_KEY`, `TAVILY_API_KEY`, `GROQ_MODEL`

---

### Task 2: Web search tool (Tavily)

**Files:**
- Create: `agent/tools/web_search.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1:** Write failing test `test_web_search_returns_results` with mocked Tavily client
- [ ] **Step 2:** Implement `web_search` tool using `tavily-python`
- [ ] **Step 3:** Run `pytest tests/test_tools.py::test_web_search_returns_results -v` → PASS

---

### Task 3: Web scrape tool (Playwright)

**Files:**
- Create: `agent/tools/web_scrape.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1:** Write failing test with mocked page HTML
- [ ] **Step 2:** Implement async scrape → sync wrapper for LangChain tool
- [ ] **Step 3:** Run `pytest tests/test_tools.py -k web_scrape -v` → PASS

---

### Task 4: LangGraph agent

**Files:**
- Create: `agent/tools/__init__.py`, `agent/graph.py`, `run_agent.py`
- Test: `tests/test_graph.py`

- [ ] **Step 1:** `get_all_tools()` returns both tools
- [ ] **Step 2:** `build_agent()` returns compiled graph with Groq model from env
- [ ] **Step 3:** Test graph compiles without network (`test_build_agent_compiles`)
- [ ] **Step 4:** CLI: `python run_agent.py "<prompt>"`

---

### Task 5: End-to-end smoke

- [ ] **Step 1:** `pip install -r requirements.txt && playwright install chromium`
- [ ] **Step 2:** `pytest -v`
- [ ] **Step 3:** `python run_agent.py "Search for LangGraph agent tutorials and summarize in 3 bullets"`

---

## Self-review (spec coverage)

- [x] LangGraph + ChatGroq → Task 4
- [x] Tavily web search → Task 2
- [x] Playwright scraper → Task 3
- [x] Groq tool-calling E2E → Task 5 CLI
- [x] Unit tests per tool → Tasks 2–3
- [x] Test prompt "Search X and summarize" → Task 5
