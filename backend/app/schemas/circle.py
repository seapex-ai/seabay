from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CircleContactMode, CircleJoinMode


class CircleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=500)
    join_mode: CircleJoinMode = CircleJoinMode.INVITE_ONLY
    contact_mode: CircleContactMode = CircleContactMode.REQUEST_ONLY
    max_members: int = Field(30, ge=2, le=30)


class CircleUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=128)
    description: str | None = Field(None, max_length=500)
    join_mode: CircleJoinMode | None = None
    contact_mode: CircleContactMode | None = None


class CircleJoinRequest(BaseModel):
    invite_token: str | None = None  # for invite_only or open_link


class CircleJoinRequestSubmit(BaseModel):
    message: str | None = Field(None, max_length=500)


class CircleResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner_agent_id: str
    join_mode: str
    contact_mode: str
    max_members: int
    member_count: int
    is_active: bool
    invite_link_token: str | None = None
    created_at: datetime


class CircleMemberResponse(BaseModel):
    agent_id: str
    display_name: str
    role: str
    joined_at: datetime


class CircleJoinRequestResponse(BaseModel):
    id: str
    circle_id: str
    agent_id: str
    message: str | None = None
    status: str
    created_at: datetime
