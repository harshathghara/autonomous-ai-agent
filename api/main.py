"""FastAPI app — REST API, WebSocket streaming, OAuth, and static HTML UI."""

import sys
from pathlib import Path

# Allow `python api/main.py` (script) as well as `python -m api.main` (package).
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from agent.web_confirmation import (
    activate_web_confirmation,
    deactivate_web_confirmation,
    get_web_confirmation_broker,
    init_web_confirmation_broker,
)
from api.broadcast import broadcaster
from api.schemas import StepOut, TaskCreate, TaskSummary
from api.startup import auto_migrate_enabled, validate_env
from auth.oauth_routes import router as oauth_router
from auth.token_store import default_user_id
from db.migrate import run_alembic_upgrade
from db.repositories import steps as steps_repo
from db.repositories import tasks as tasks_repo
from db.session import AsyncSessionLocal

load_dotenv()

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_running_tasks: dict[uuid.UUID, asyncio.Task] = {}

init_web_confirmation_broker(broadcaster.publish)


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = validate_env()
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    if auto_migrate_enabled():
        logger.info("Running Alembic migrations (AUTO_MIGRATE=true)")
        run_alembic_upgrade()

    async with AsyncSessionLocal() as db:
        stale = await tasks_repo.mark_stale_running_tasks_failed(db)
    if stale:
        logger.warning("Marked %s orphaned running task(s) as failed on startup", stale)

    yield

    for task in list(_running_tasks.values()):
        if not task.done():
            task.cancel()
    _running_tasks.clear()


app = FastAPI(title="Autonomous AI Agent", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["TOKEN_ENCRYPTION_KEY"],
    max_age=600,
    same_site="lax",
    https_only=False,
)
app.include_router(oauth_router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="UI not found — missing static/index.html")
    return FileResponse(index_path)


@app.get("/api/health")
async def health():
    """Liveness/readiness probe — checks PostgreSQL connectivity."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": str(exc)},
        ) from exc


@app.get("/api/tasks", response_model=list[TaskSummary])
async def list_tasks():
    user_id = default_user_id()
    async with AsyncSessionLocal() as db:
        rows = await tasks_repo.get_tasks_for_user(db, user_id)
        counts = await tasks_repo.get_user_turn_counts(db, [t.id for t in rows])
    return [
        TaskSummary(
            id=t.id,
            input=t.input,
            status=t.status,
            final_output=t.final_output,
            created_at=t.created_at,
            completed_at=t.completed_at,
            message_count=counts.get(t.id, 1),
        )
        for t in rows
    ]


async def _task_summary(task, *, message_count: int | None = None) -> TaskSummary:
    if message_count is None:
        async with AsyncSessionLocal() as db:
            counts = await tasks_repo.get_user_turn_counts(db, [task.id])
        message_count = counts.get(task.id, 1)
    return TaskSummary(
        id=task.id,
        input=task.input,
        status=task.status,
        final_output=task.final_output,
        created_at=task.created_at,
        completed_at=task.completed_at,
        message_count=message_count,
    )


@app.get("/api/tasks/{task_id}", response_model=TaskSummary)
async def get_task(task_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        task = await tasks_repo.get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return await _task_summary(task)


@app.get("/api/tasks/{task_id}/steps", response_model=list[StepOut])
async def get_task_steps(task_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        if await tasks_repo.get_task_by_id(db, task_id) is None:
            raise HTTPException(status_code=404, detail="Task not found")
        steps = await steps_repo.get_steps_for_task(db, task_id)
    return [
        StepOut(
            step_number=s.step_number,
            step_type=s.step_type,
            tool_name=s.tool_name,
            tool_input=s.tool_input,
            tool_output=s.tool_output,
            reasoning=s.reasoning,
            created_at=s.created_at,
        )
        for s in steps
    ]


def _steps_to_events(steps: list) -> list[dict]:
    events: list[dict] = []
    for step in steps:
        if step.step_type == "user" and step.reasoning:
            events.append({"type": "user", "content": step.reasoning})
        elif step.step_type == "thought" and step.reasoning:
            events.append({"type": "thought", "content": step.reasoning})
        elif step.step_type == "tool_call":
            events.append(
                {"type": "tool_call", "name": step.tool_name, "input": step.tool_input or {}}
            )
        elif step.step_type == "observation":
            events.append(
                {
                    "type": "tool_result",
                    "name": step.tool_name,
                    "content": step.tool_output or "",
                }
            )
    return events


async def _run_task_background(
    task_id: uuid.UUID,
    prompt: str,
    auto_approve: bool,
    *,
    continue_chat: bool = False,
) -> None:
    from agent.runner import run_agent_task

    await asyncio.sleep(0.05)

    async def on_event(event: dict) -> None:
        await broadcaster.publish(task_id, event)

    loop = asyncio.get_running_loop()
    activate_web_confirmation(task_id, loop)
    try:
        await run_agent_task(
            prompt,
            task_id=task_id,
            auto_approve=auto_approve,
            continue_chat=continue_chat,
            on_event=on_event,
        )
    except Exception:
        pass  # runner already emits error event and marks task failed
    finally:
        deactivate_web_confirmation()
        _running_tasks.pop(task_id, None)


@app.post("/api/tasks", response_model=TaskSummary)
async def create_task(body: TaskCreate):
    from agent.persistence import create_task_record

    continue_chat = body.continue_task_id is not None
    if continue_chat:
        task_id = body.continue_task_id
        assert task_id is not None
        async with AsyncSessionLocal() as db:
            task = await tasks_repo.get_task_by_id(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status == "running" or task_id in _running_tasks:
            raise HTTPException(status_code=409, detail="Task is already running")
    else:
        task_id = await create_task_record(body.input)

    _running_tasks[task_id] = asyncio.create_task(
        _run_task_background(
            task_id,
            body.input,
            body.auto_approve,
            continue_chat=continue_chat,
        )
    )
    async with AsyncSessionLocal() as db:
        task = await tasks_repo.get_task_by_id(db, task_id)
        counts = await tasks_repo.get_user_turn_counts(db, [task_id])
    assert task is not None
    return await _task_summary(task, message_count=counts.get(task_id, 1))


@app.delete("/api/tasks/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID):
    user_id = default_user_id()
    async with AsyncSessionLocal() as db:
        task = await tasks_repo.get_task_by_id(db, task_id)
        if task is None or task.user_id != user_id:
            raise HTTPException(status_code=404, detail="Task not found")

    running = _running_tasks.pop(task_id, None)
    if running and not running.done():
        running.cancel()

    async with AsyncSessionLocal() as db:
        deleted = await tasks_repo.delete_task(db, task_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")


@app.websocket("/api/tasks/{task_id}/stream")
async def stream_task(task_id: uuid.UUID, websocket: WebSocket):
    async with AsyncSessionLocal() as db:
        task = await tasks_repo.get_task_by_id(db, task_id)
    if task is None:
        await websocket.close(code=4404)
        return

    await broadcaster.subscribe(task_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "task_id": str(task_id), "status": task.status})
        live_only = websocket.query_params.get("live") == "1"
        if not live_only:
            async with AsyncSessionLocal() as db:
                steps = await steps_repo.get_steps_for_task(db, task_id)
            for event in _steps_to_events(steps):
                await websocket.send_json(event)
        broker = get_web_confirmation_broker()
        if broker:
            for event in broker.pending_events_for_task(task_id):
                await websocket.send_json(event)
        if task.final_output and task.status in ("completed", "failed"):
            await websocket.send_json(
                {"type": "final" if task.status == "completed" else "error", "content": task.final_output}
            )
        while True:
            raw = await websocket.receive_text()
            if not raw or not broker:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "confirmation_response":
                broker.resolve(
                    data.get("confirmation_id", ""),
                    bool(data.get("approved")),
                )
    except WebSocketDisconnect:
        broadcaster.unsubscribe(task_id, websocket)


def main() -> None:
    host = os.getenv("API_HOST", "localhost")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
