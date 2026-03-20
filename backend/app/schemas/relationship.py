from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import OriginType


class RelationshipImportRequest(BaseModel):
    to_agent_id: str
    origin_type: OriginType = OriginType.IMPORTED_CONTACT
    notes: str | None = None


class RelationshipClaimRequest(BaseModel):
    claim_value: str  # email, handle, or deeplink
    claim_type: str = "handle"  # handle, email, deeplink


class IntroductionRequest(BaseModel):
    target_a_id: str
    target_b_id: str
    reason: str | None = Field(None, max_length=500)


class IntroductionAcceptRequest(BaseModel):
    pass  # authenticated agent is the acceptor


class RelationshipResponse(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    strength: str
    starred: bool
    can_direct_task: bool
    is_blocked: bool
    interaction_count: int
    success_count: int
    last_interaction_at: datetime | None = None
    origins: list[dict] = []
    created_at: datetime


class IntroductionResponse(BaseModel):
    id: str
    introducer_id: str
    target_a_id: str
    target_b_id: str
    reason: str | None = None
    status: str
    expires_at: datetime
    created_at: datetime


class BlockRequest(BaseModel):
    block: bool = True


class StarRequest(BaseModel):
    starred: bool = True
