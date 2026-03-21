"""Match endpoint — POST /v1/match.

Top-level matching API that orchestrates intent creation, candidate matching,
and bucket formation. Part of Remote MCP Server v1.0 spec (P1 tool: match_request).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.database import get_db
from app.models.agent import Agent
from app.schemas.match import MatchRequest, MatchResponse
from app.services import match_service

router = APIRouter()


@router.post("", status_code=200)
async def match_request(
    req: MatchRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """POST /v1/match — Top-level match request.

    Accepts a natural-language description plus structured fields (skills,
    languages, location, audience_scope, time_window). Internally creates
    an intent, runs matching, and returns bucketed candidates with a
    human-readable summary and fallback URL.

    Returns:
        recommended_action: Suggested next step (e.g. create_task with best match)
        candidate_buckets: {top_matches, also_relevant}
        summary_text: Human-readable summary for LLM consumption
        fallback_url: Web URL for non-MCP fallback
    """
    result = await match_service.match_request(
        db,
        agent=current_agent,
        description=req.description,
        skills=req.skills or None,
        languages=req.languages or None,
        location=req.location,
        audience_scope=req.audience_scope,
        time_window=req.time_window,
    )
    return MatchResponse(**result)
