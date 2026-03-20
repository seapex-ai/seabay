"""SSE event schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SSEvent(BaseModel):
    """Server-Sent Event payload."""
    event: str
    data: dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None


class EventStatusResponse(BaseModel):
    """SSE connection status."""
    connected_agents: int
    your_connections: int


class TaskEvent(BaseModel):
    """Task lifecycle event payload."""
    event_type: str  # task.created, task.accepted, task.completed, etc.
    task_id: str
    status: str
    from_agent_id: Optional[str] = None
    to_agent_id: Optional[str] = None
    risk_level: Optional[str] = None
    timestamp: datetime


class IntroductionEvent(BaseModel):
    """Introduction event payload."""
    event_type: str  # introduction.pending, introduction.accepted, etc.
    introduction_id: str
    introducer_id: str
    target_a_id: str
    target_b_id: str
    status: str
    timestamp: datetime


class CircleEvent(BaseModel):
    """Circle event payload."""
    event_type: str  # circle.member_joined, circle.request_submitted
    circle_id: str
    agent_id: str
    timestamp: datetime
