"""Tests for web-based confirmation broker."""

import asyncio
import uuid

import pytest

from agent.web_confirmation import WebConfirmationBroker


@pytest.mark.asyncio
async def test_broker_request_and_resolve():
    published: list[dict] = []

    async def publish(task_id, event):
        published.append(event)

    broker = WebConfirmationBroker(publish)
    task_id = uuid.uuid4()

    async def approve_later():
        await asyncio.sleep(0.01)
        broker.resolve(published[0]["confirmation_id"], True)

    asyncio.create_task(approve_later())
    approved = await broker.request(task_id, "calendar_write", {"summary": "Test"})
    assert approved is True
    assert published[0]["type"] == "confirmation_required"


def test_broker_resolve_denied():
    async def publish(task_id, event):
        pass

    broker = WebConfirmationBroker(publish)
    assert broker.resolve("missing-id", True) is False


@pytest.mark.asyncio
async def test_broker_replays_pending_on_late_subscriber():
    published: list[dict] = []

    async def publish(task_id, event):
        published.append(event)

    broker = WebConfirmationBroker(publish)
    task_id = uuid.uuid4()

    async def deny_later():
        await asyncio.sleep(0.01)
        broker.resolve(published[0]["confirmation_id"], False)

    asyncio.create_task(deny_later())
    request_task = asyncio.create_task(broker.request(task_id, "email_send", {"to": "me"}))
    await asyncio.sleep(0.005)
    pending = broker.pending_events_for_task(task_id)
    assert len(pending) == 1
    assert pending[0]["type"] == "confirmation_required"
    assert await request_task is False
