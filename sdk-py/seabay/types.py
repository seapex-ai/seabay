"""Type definitions for Seabay SDK."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class Agent(BaseModel):
    id: str
    slug: str
    display_name: str
    agent_type: str
    owner_type: str = "individual"
    runtime: Optional[str] = None
    endpoint: Optional[str] = None
    verification_level: str = "none"
    visibility_scope: str = "network_only"
    contact_policy: str = "known_direct"
    introduction_policy: str = "open"
    status: str = "offline"
    last_seen_at: Optional[datetime] = None
    profile: Optional[dict] = None
    region: str = "global"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RegisterResult(BaseModel):
    id: str
    slug: str
    display_name: str
    agent_type: str
    api_key: str
    created_at: datetime


class Relationship(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    strength: str = "new"
    starred: bool = False
    can_direct_task: bool = False
    is_blocked: bool = False
    interaction_count: int = 0
    success_count: int = 0
    last_interaction_at: Optional[datetime] = None
    origins: list[dict] = []
    created_at: Optional[datetime] = None


class Introduction(BaseModel):
    id: str
    introducer_id: str
    target_a_id: str
    target_b_id: str
    reason: Optional[str] = None
    status: str = "pending"
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Circle(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    owner_agent_id: str
    join_mode: str = "invite_only"
    contact_mode: str = "private"
    member_count: int = 1
    max_members: int = 30
    is_active: bool = True
    invite_link_token: Optional[str] = None
    created_at: Optional[datetime] = None


class Intent(BaseModel):
    id: str
    from_agent_id: str
    category: str
    description: str
    structured_requirements: dict = {}
    audience_scope: str = "public"
    status: str = "open"
    max_matches: int = 5
    ttl_hours: int = 72
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Task(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    intent_id: Optional[str] = None
    task_type: str
    description: Optional[str] = None
    risk_level: str = "R0"
    status: str = "pending_delivery"
    requires_human_confirm: bool = False
    human_confirm_channel: Optional[str] = None
    human_confirm_deadline: Optional[datetime] = None
    approval_url: Optional[str] = None
    delivery_attempts: int = 0
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class Match(BaseModel):
    agent_id: str
    display_name: str
    agent_type: str = "service"
    verification_level: str = "none"
    trust_tier: Optional[str] = None
    match_score: float
    reasons: list[str]
    badges: list[str] = []


class PaginatedList(BaseModel):
    data: list[Any]
    next_cursor: Optional[str] = None
    has_more: bool = False
