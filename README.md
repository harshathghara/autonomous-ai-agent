# Autonomous AI Agent

Personal AI agent: natural language → multi-step tasks across web, email, and calendar.

**Stack:** Groq · LangGraph · PostgreSQL · FastAPI · plain HTML/JS UI (see [autonomous_ai_agent_project_plan.md](./autonomous_ai_agent_project_plan.md))

## Current status

| Week | Status | What's built |
|------|--------|--------------|
| **Week 1** | ✅ Done | LangGraph ReAct agent, Tavily search, Playwright scrape |
| **Week 2** | ✅ Done | PostgreSQL + Alembic, Google OAuth (Gmail), email read/send |
| **Week 3** | ✅ Done | Google Calendar read/write/delete, step persistence, task resume, verbose CLI |
| **Week 4** | ✅ Done | Memory tools, CLI confirmation, workflow E2E tests, error recovery |
| **Week 5** | ✅ Done | FastAPI + WebSocket + HTML chat UI, in-browser OAuth, web confirmation |
| **Week 6** | ✅ Polish done | Auto-migrations, health check, rate-limit retry, orphan task cleanup |
| **Week 6** | ⏳ Deploy later | Docker Compose, Railway (not implemented yet) |

### Tools available today

| Tool | Description |
|------|-------------|
| `web_search` | Tavily web search |
| `web_scrape` | Playwright page scrape |
| `email_read` | Gmail inbox |
| `email_send` | Gmail send (`to='me'` for "mail me") |
| `calendar_read` | List upcoming events |
| `calendar_write` | Create events |
| `calendar_delete` | Remove events by ID or title |
| `memory_read` | List saved user preferences |
| `memory_save` | Save a preference for future sessions |
| `memory_delete` | Remove an outdated preference |

**61 tests passing.** Multi-step manual test: [docs/manual_workflow_test.md](./docs/manual_workflow_test.md)

## What is “production polish”?

Production polish is everything that makes the app **reliable to run locally** without manual babysitting — distinct from **deployment** (Docker, cloud hosting):

| Polish (done) | Deployment (later) |
|---------------|-------------------|
| Auto-run Alembic migrations on API startup (`AUTO_MIGRATE`) | Docker Compose |
| `/api/health` — DB connectivity probe | Railway / cloud deploy |
| Mark stuck `running` chats as failed after server restart | Demo GIF / video (you record) |
| Groq rate-limit retry with exponential backoff | |
| Connection pool tuning (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) | |
| Required env validation on startup | |
| Graceful cancel of background tasks on shutdown | |

## Architecture

```mermaid
flowchart TB
  subgraph client [Browser]
    UI[HTML/CSS/JS Chat UI]
  end

  subgraph api [FastAPI :8000]
    REST[REST /api/tasks]
    WS[WebSocket stream]
    OAuth[OAuth /auth/google]
    Health[/api/health]
  end

  subgraph agent [Agent core]
    Runner[agent/runner.py]
    Graph[LangGraph ReAct + Groq]
    Tools[web · email · calendar · memory]
  end

  subgraph data [PostgreSQL]
    Tasks[agent_tasks]
    Steps[agent_steps]
    Memory[agent_memory]
    Tokens[oauth_tokens encrypted]
  end

  UI --> REST
  UI --> WS
  UI --> OAuth
  REST --> Runner
  WS --> Runner
  Runner --> Graph
  Graph --> Tools
  Runner --> Tasks
  Runner --> Steps
  Tools --> Tokens
  Graph --> Memory
```

Both entry points share the same agent:

```
PostgreSQL
    ├── python -m api.main     → Web UI + API + OAuth (port 8000)
    └── python run_agent.py    → CLI only
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
playwright install chromium
cp .env.example .env           # fill in keys (see below)
```

Generate a token encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add it to `.env` as `TOKEN_ENCRYPTION_KEY`.

### Database

Create the database. Migrations run automatically when you start the API (`AUTO_MIGRATE=true` by default). To run manually:

```bash
venv\Scripts\alembic upgrade head
```

Set `AUTO_MIGRATE=false` if you prefer to migrate by hand.

### Google OAuth (Gmail + Calendar)

1. Create OAuth credentials in [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (Web application).
2. Add redirect URI: `http://localhost:8000/auth/callback`
3. Enable **Gmail API** and **Google Calendar API** for the project.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `USER_EMAIL` in `.env`.

Connect your account from the web UI (**Connect Google** button) after starting the server below.

### Timezone

The agent reads your **Google Calendar timezone** automatically. Set `USER_TIMEZONE` in `.env` only as a fallback (e.g. `UTC`).

## Run tests

```bash
pytest -v
```

## Web UI (recommended)

PostgreSQL must be running. Start the server:

```bash
python -m api.main
# or
python api/main.py
```

Open [http://localhost:8000](http://localhost:8000). Health check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

| Feature | Details |
|---------|---------|
| Chat | Multi-turn conversations with live step streaming |
| Chat history | One session per row; delete with trash icon |
| Connect Google | One-click OAuth on the same port |
| Auto-approve | Skip confirmation for email/calendar actions |
| Confirmation | Approve / Deny buttons in chat when auto-approve is off |
| + New chat | Start a fresh conversation thread |

Configure host/port via `API_HOST` and `API_PORT` in `.env` (default `localhost:8000`).

## Run agent (CLI)

```bash
python run_agent.py "What meetings do I have next week?"
python run_agent.py -v "Search for Python conferences 2026 and summarize"
python run_agent.py -y "Schedule a meeting tomorrow at 10 am named daily standup"
python run_agent.py --resume --task-id <uuid-from-previous-run>
```

Each new CLI run creates a task in PostgreSQL. Resume is CLI-only; the web UI continues chats in the same session.

## Project layout

```
AI Agent/
├── agent/                    # LangGraph agent core
│   ├── graph.py              # Groq LLM + system prompt (live date/time, memory)
│   ├── runner.py             # Shared execution for CLI + API; streams events
│   ├── persistence.py        # Save/load tasks & steps; rebuild state for resume/follow-up
│   ├── memory.py             # Long-term preferences (agent_memory table)
│   ├── summarize.py          # Saves last_task_summary after long runs (8+ steps)
│   ├── errors.py             # Tool error formatting + retry hints + safe wrapper
│   ├── llm_errors.py         # Groq error parsing, rate-limit retry backoff
│   ├── confirmation.py       # CLI + web confirmation wrapper for destructive tools
│   ├── web_confirmation.py   # WebSocket approval broker (Approve / Deny in UI)
│   └── tools/
│       ├── __init__.py       # Registers all tools; applies safe + confirmation wrappers
│       ├── web_search.py     # Tavily web search
│       ├── web_scrape.py     # Playwright page scrape
│       ├── email.py          # Gmail read/send
│       ├── calendar.py       # Google Calendar read/write/delete
│       └── memory_tools.py   # memory_read / memory_save / memory_delete
│
├── api/                      # FastAPI web server
│   ├── main.py               # REST, WebSocket, OAuth mount, static UI, lifespan startup
│   ├── schemas.py            # Pydantic request/response models
│   ├── broadcast.py          # WebSocket fan-out to connected clients
│   └── startup.py            # Env validation, AUTO_MIGRATE flag
│
├── auth/                     # Google OAuth
│   ├── oauth_routes.py       # /auth/google and /auth/callback
│   ├── token_store.py        # Encrypted token storage (async + sync loaders)
│   └── login_server.py       # Optional standalone OAuth server (legacy)
│
├── db/                       # PostgreSQL layer
│   ├── models.py             # agent_tasks, agent_steps, agent_memory, oauth_tokens
│   ├── session.py            # Async SQLAlchemy engine + connection pool
│   ├── url.py                # DATABASE_URL builder from DB_* env vars
│   ├── migrate.py            # Programmatic Alembic upgrade (used on API startup)
│   └── repositories/
│       ├── tasks.py          # Task CRUD, chat turn counts, orphan cleanup
│       ├── steps.py          # Agent step persistence
│       ├── memory.py         # Preference upsert/list
│       └── tokens.py         # OAuth token read/write
│
├── static/                   # Plain HTML chat UI (no React)
│   ├── index.html            # Layout: sidebar, chat feed, input form
│   ├── app.js                # WebSocket client, chat history, delete, follow-ups
│   └── style.css             # Dark theme, timeline, tool-call cards
│
├── alembic/                  # Database migrations
│   ├── env.py                # Alembic runtime config
│   └── versions/
│       └── 001_initial_schema.py
│
├── tests/                    # pytest suite (61 tests)
│   ├── conftest.py           # API keys, DB env, Fernet fixtures
│   ├── test_api.py           # FastAPI routes + health
│   ├── test_runner.py        # Event extraction from LangChain messages
│   ├── test_workflow_e2e.py  # Multi-tool workflow chains
│   └── test_*.py             # Per-module unit tests (tools, memory, calendar, …)
│
├── docs/
│   └── manual_workflow_test.md   # Step-by-step manual E2E checklist
│
├── run_agent.py              # CLI entry point (--verbose, --resume, --yes)
├── alembic.ini               # Alembic CLI config
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── pytest.ini                # Pytest config
├── README.md                 # This file
└── autonomous_ai_agent_project_plan.md   # Full week-by-week build plan
```

### Key files at a glance

| Path | Role |
|------|------|
| `run_agent.py` | CLI — run one-off tasks from the terminal |
| `api/main.py` | Web server — UI, REST API, WebSocket streaming, OAuth |
| `agent/runner.py` | Single execution path used by both CLI and web |
| `agent/graph.py` | Builds the LangGraph ReAct agent bound to Groq + tools |
| `agent/persistence.py` | Writes every agent step to PostgreSQL in real time |
| `static/app.js` | Chat UI logic — multi-turn sessions, live steps, delete history |
| `db/repositories/tasks.py` | Task list, delete, stale `running` cleanup on startup |
| `db/migrate.py` | Runs `alembic upgrade head` when `AUTO_MIGRATE=true` |

## What's next (deployment only)

- Docker Compose (app + PostgreSQL)
- Deploy to Railway or similar
- Record a short demo video for your portfolio

See [autonomous_ai_agent_project_plan.md](./autonomous_ai_agent_project_plan.md) for the full roadmap.
