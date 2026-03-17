"""Report schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    reason_code: str = Field(
        ..., description="spam, impersonation, unsafe_request, policy_violation, harassment, other",
    )
    notes: Optional[str] = Field(None, max_length=2000)
    task_id: Optional[str] = Field(None, description="Related task ID if applicable")


class ReportResponse(BaseModel):
    id: str
    reporter_agent_id: str
    reported_agent_id: str
    task_id: Optional[str] = None
    reason_code: str
    notes: Optional[str] = None
    status: str
    created_at: Optional[str] = None
