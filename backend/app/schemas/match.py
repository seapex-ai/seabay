"""Match request/response schemas for POST /v1/match."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=1, max_length=2000)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    location: str | None = None
    audience_scope: str = "public"
    time_window: str | None = Field(
        None,
        description="ISO-8601 duration or human-readable window, e.g. 'this_weekend', '24h'",
    )


class MatchCandidate(BaseModel):
    agent_id: str
    display_name: str
    description: str | None = None
    location: str | None = None
    skills: list[str] = []
    verification_level: str = "none"
    last_active: str | None = None
    trust_summary: dict = {}
    why_matched: list[str] = []
    match_score: float = 0.0


class CandidateBuckets(BaseModel):
    top_matches: list[MatchCandidate] = []
    also_relevant: list[MatchCandidate] = []


class SuggestedAction(BaseModel):
    type: str
    target_id: str | None = None
    reason: str


class MatchResponse(BaseModel):
    recommended_action: SuggestedAction | None = None
    candidate_buckets: CandidateBuckets
    summary_text: str
    fallback_url: str
    intent_id: str | None = None
    total_matches: int = 0
