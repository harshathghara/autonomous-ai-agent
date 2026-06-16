"""Pydantic models for the FastAPI layer."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    input: str = Field(..., min_length=1, description="Natural-language task for the agent")
    auto_approve: bool = Field(
        True,
        description="Skip confirmation for email send and calendar write/delete (required for web UI)",
    )
    continue_task_id: uuid.UUID | None = Field(
        None,
        description="Continue an existing conversation instead of starting a new task",
    )


class TaskSummary(BaseModel):
    id: uuid.UUID
    input: str
    status: str
    final_output: str | None
    created_at: datetime
    completed_at: datetime | None
    message_count: int = Field(1, description="User turns in this chat session")


class StepOut(BaseModel):
    step_number: int
    step_type: str
    tool_name: str | None
    tool_input: dict | None
    tool_output: str | None
    reasoning: str | None
    created_at: datetime
