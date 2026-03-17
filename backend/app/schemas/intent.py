from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IntentCategory


class IntentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: IntentCategory
    description: str = Field(..., min_length=1, max_length=2000)
    structured_requirements: dict = {}
    audience_scope: str = "public"  # public, network, circle:{id}
    ttl_hours: int = Field(72, ge=1, le=168)
    max_matches: int = Field(5, ge=1, le=20)


class IntentResponse(BaseModel):
    id: str
    from_agent_id: str
    category: str
    description: str
    structured_requirements: dict = {}
    audience_scope: str
    status: str
    max_matches: int
    ttl_hours: int
    expires_at: datetime
    created_at: datetime


class IntentMatchResponse(BaseModel):
    agent_id: str
    display_name: str
    agent_type: str
    verification_level: str
    trust_tier: str | None = None
    match_score: float
    reasons: list[str]  # min 3 reasons per spec
    badges: list[str] = []


class IntentSelectRequest(BaseModel):
    agent_id: str
    description: str | None = None
    payload_ref: str | None = None
    payload_inline: dict | None = None
