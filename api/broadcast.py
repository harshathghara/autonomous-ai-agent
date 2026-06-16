"""WebSocket broadcast helpers for live agent events."""

import asyncio
import uuid
from collections import defaultdict

from fastapi import WebSocket


class TaskBroadcaster:
    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, list[WebSocket]] = defaultdict(list)

    async def subscribe(self, task_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._subscribers[task_id].append(websocket)

    def unsubscribe(self, task_id: uuid.UUID, websocket: WebSocket) -> None:
        sockets = self._subscribers.get(task_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self._subscribers.pop(task_id, None)

    async def publish(self, task_id: uuid.UUID, event: dict) -> None:
        for ws in list(self._subscribers.get(task_id, [])):
            try:
                await ws.send_json(event)
            except Exception:
                self.unsubscribe(task_id, ws)


broadcaster = TaskBroadcaster()
