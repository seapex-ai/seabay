"""Statistics and activity schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AgentStatsResponse(BaseModel):
    """Agent activity statistics."""
    agent_id: str
    tasks_sent: int = 0
    tasks_received: int = 0
    tasks_completed: int = 0
    tasks_last_7d: int = 0
    success_rate: float = 0.0
    average_rating: float | None = None
    interactions_30d: int = 0
    profile_views_7d: int = 0
    search_appearances_7d: int = 0


class ActivityFeedItem(BaseModel):
    """Single activity feed item."""
    id: str
    type: str  # interaction, task, introduction
    from_agent_id: str | None = None
    to_agent_id: str | None = None
    outcome: str | None = None
    rating: float | None = None
    created_at: datetime


class ActivityFeedResponse(BaseModel):
    """Paginated activity feed."""
    data: list[ActivityFeedItem]
    next_cursor: str | None = None
    has_more: bool = False


class RelationshipSummary(BaseModel):
    """Relationship statistics summary."""
    total: int = 0
    by_strength: dict[str, int] = {}
    starred: int = 0
    blocked: int = 0


class AccountStatusResponse(BaseModel):
    """Account maturity status."""
    is_new_account: bool
    account_age_days: int
    days_until_established: int
    daily_limits: dict[str, int]
    restrictions: dict[str, bool]


class TrustScoreResponse(BaseModel):
    """Trust score details."""
    agent_id: str
    trust_score: float
    trust_signals: dict
    popularity_signals: dict


class TrustTrendPoint(BaseModel):
    """Single point in trust score trend."""
    date: str
    trust_score: float


class TrustTrendResponse(BaseModel):
    """Trust score trend over time."""
    agent_id: str
    days: int
    trend: list[TrustTrendPoint]


class PlatformStatsResponse(BaseModel):
    """Platform-wide statistics (admin only)."""
    agents: dict
    tasks: dict
    reports_pending: int
