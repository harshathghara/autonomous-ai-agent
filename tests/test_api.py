"""Tests for FastAPI REST endpoints and static UI."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(auth_env, groq_api_key, monkeypatch):
    monkeypatch.setenv("AUTO_MIGRATE", "false")
    with (
        patch("api.main.run_alembic_upgrade"),
        patch(
            "api.main.tasks_repo.mark_stale_running_tasks_failed",
            new_callable=AsyncMock,
            return_value=0,
        ),
    ):
        from api.main import app

        with TestClient(app) as client:
            yield client


def test_index_returns_html(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    assert "Autonomous AI Agent" in response.text


def test_list_tasks_empty(api_client):
    with patch("api.main.tasks_repo.get_tasks_for_user", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        response = api_client.get("/api/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task_starts_background_run(api_client):
    task_id = uuid.uuid4()

    async def fake_create(prompt):
        return task_id

    mock_task = type(
        "Task",
        (),
        {
            "id": task_id,
            "input": "hello",
            "status": "running",
            "final_output": None,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "completed_at": None,
        },
    )()

    async def noop_background(*_args, **_kwargs):
        return None

    with (
        patch("agent.persistence.create_task_record", side_effect=fake_create),
        patch("api.main.tasks_repo.get_task_by_id", new_callable=AsyncMock, return_value=mock_task),
        patch("api.main.tasks_repo.get_user_turn_counts", new_callable=AsyncMock, return_value={task_id: 1}),
        patch("api.main._run_task_background", side_effect=noop_background),
    ):
        response = api_client.post("/api/tasks", json={"input": "hello", "auto_approve": True})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task_id)
    assert data["status"] == "running"


def test_get_task_not_found(api_client):
    with patch("api.main.tasks_repo.get_task_by_id", new_callable=AsyncMock, return_value=None):
        response = api_client.get(f"/api/tasks/{uuid.uuid4()}")
    assert response.status_code == 404


def test_delete_task_not_found(api_client):
    with patch("api.main.tasks_repo.get_task_by_id", new_callable=AsyncMock, return_value=None):
        response = api_client.delete(f"/api/tasks/{uuid.uuid4()}")
    assert response.status_code == 404


def test_delete_task_running(api_client):
    task_id = uuid.uuid4()
    mock_task = type(
        "Task",
        (),
        {
            "id": task_id,
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "status": "running",
        },
    )()
    with (
        patch("api.main.tasks_repo.get_task_by_id", new_callable=AsyncMock, return_value=mock_task),
        patch("api.main.tasks_repo.delete_task", new_callable=AsyncMock, return_value=True),
    ):
        response = api_client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 204


def test_health_ok(api_client):
    with patch("api.main.AsyncSessionLocal") as mock_session:
        session = mock_session.return_value.__aenter__.return_value
        session.execute = AsyncMock()
        response = api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
