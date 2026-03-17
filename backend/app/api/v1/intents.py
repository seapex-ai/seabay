"""Intent management — 4 endpoints.

Refactored to use intent_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.core.exceptions import InvalidRequestError
from app.database import get_db
from app.models.agent import Agent
from app.schemas.intent import IntentCreateRequest, IntentResponse, IntentSelectRequest
from app.services import intent_service

router = APIRouter()


@router.post("", status_code=201)
async def create_intent(
    req: IntentCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> IntentResponse:
    """POST /v1/intents — Publish Intent."""
    intent = await intent_service.create_intent(
        db,
        agent=current_agent,
        category=req.category.value,
        description=req.description,
        structured_requirements=req.structured_requirements,
        audience_scope=req.audience_scope,
        ttl_hours=req.ttl_hours,
        max_matches=req.max_matches,
    )
    return _intent_to_response(intent)


@router.get("/{intent_id}")
async def get_intent(
    intent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> IntentResponse:
    """GET /v1/intents/{id} — Get Intent details."""
    intent = await intent_service.get_intent(db, intent_id)
    return _intent_to_response(intent)


@router.get("/{intent_id}/matches")
async def get_matches(
    intent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/intents/{id}/matches — Get matching Agent candidates.

    V1.5 uses rules-first matching: skill overlap, language overlap, location.
    Each match must have >= 3 reasons per spec.
    """
    intent = await intent_service.get_intent(db, intent_id)
    if intent.from_agent_id != current_agent.id:
        raise InvalidRequestError("Can only view matches for your own intents")

    matches = await intent_service.find_matches(db, intent, current_agent)

    if matches:
        intent.status = "matched"
        await db.flush()

    return {"data": matches, "intent_id": intent_id, "total": len(matches)}


@router.post("/{intent_id}/cancel")
async def cancel_intent(
    intent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> IntentResponse:
    """POST /v1/intents/{id}/cancel — Cancel Intent."""
    intent = await intent_service.get_intent(db, intent_id)
    if intent.from_agent_id != current_agent.id:
        raise InvalidRequestError("Can only cancel your own intents")
    if intent.status in ("fulfilled", "expired", "cancelled"):
        raise InvalidRequestError(f"Intent is already {intent.status}")
    intent.status = "cancelled"
    await db.flush()
    return _intent_to_response(intent)


@router.post("/{intent_id}/select")
async def select_candidate(
    intent_id: str,
    req: IntentSelectRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/intents/{id}/select — Select candidate and create Task."""
    intent = await intent_service.get_intent(db, intent_id)
    task = await intent_service.select_candidate(
        db,
        intent=intent,
        agent=current_agent,
        selected_agent_id=req.agent_id,
        description=req.description,
        payload_ref=req.payload_ref,
        payload_inline=req.payload_inline,
    )
    return {
        "task_id": task.id,
        "intent_id": intent_id,
        "to_agent_id": req.agent_id,
        "risk_level": task.risk_level,
        "status": task.status,
    }


def _intent_to_response(intent) -> IntentResponse:
    return IntentResponse(
        id=intent.id,
        from_agent_id=intent.from_agent_id,
        category=intent.category,
        description=intent.description,
        structured_requirements=intent.structured_requirements or {},
        audience_scope=intent.audience_scope,
        status=intent.status,
        max_matches=intent.max_matches,
        ttl_hours=intent.ttl_hours,
        expires_at=intent.expires_at,
        created_at=intent.created_at,
    )
