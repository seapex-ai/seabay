from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import RiskLevel, TaskType


class TaskCreateRequest(BaseModel):
    to_agent_id: str
    task_type: TaskType
    description: str | None = Field(None, max_length=2000)
    payload_ref: str | None = None
    payload_inline: dict | None = None
    risk_level: RiskLevel = RiskLevel.R0
    ttl_seconds: int = Field(259200, ge=60, le=604800)  # 1min ~ 7days
    idempotency_key: str | None = None  # UUID, 24h dedup window


class TaskResponse(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    intent_id: str | None = None
    task_type: str
    description: str | None = None
    risk_level: str
    status: str
    requires_human_confirm: bool
    human_confirm_channel: str | None = None
    human_confirm_deadline: datetime | None = None
    approval_url: str | None = None  # for R2/R3 hosted web
    delivery_attempts: int
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None


class TaskAcceptRequest(BaseModel):
    pass


class TaskDeclineRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


class TaskHumanConfirmRequest(BaseModel):
    confirmed: bool
    token: str  # approval token, not API key


class TaskCompleteRequest(BaseModel):
    rating: float | None = Field(None, ge=1.0, le=5.0)
    notes: str | None = None


class TaskCancelRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


class TaskInboxQuery(BaseModel):
    status: str | None = None  # filter by status
    cursor: str | None = None
    limit: int = Field(20, ge=1, le=100)
