"""Relationship management — 8 endpoints.

Refactored to use relationship_service and introduction_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.agent import Agent
from app.models.relationship import RelationshipEdge
from app.schemas.relationship import (
    BlockRequest,
    IntroductionRequest,
    IntroductionResponse,
    RelationshipClaimRequest,
    RelationshipImportRequest,
    RelationshipResponse,
    StarRequest,
)
from app.services import budget_service, introduction_service, relationship_service

router = APIRouter()


@router.post("/import", status_code=201)
async def import_relationship(
    req: RelationshipImportRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> RelationshipResponse:
    """POST /v1/relationships/import — Import contact (single-direction)."""
    from app.core.exceptions import ConflictError, InvalidRequestError

    if req.to_agent_id == current_agent.id:
        raise InvalidRequestError("Cannot import self")

    target = await db.execute(select(Agent).where(Agent.id == req.to_agent_id))
    if not target.scalar_one_or_none():
        raise NotFoundError("Target agent")

    edge = await relationship_service.get_edge(db, current_agent.id, req.to_agent_id)

    if edge:
        has_origin = await relationship_service.has_origin_type(
            db, current_agent.id, req.to_agent_id, req.origin_type.value,
        )
        if has_origin:
            raise ConflictError(message="This relationship origin already exists")
    else:
        edge = await relationship_service.get_or_create_edge(
            db, current_agent.id, req.to_agent_id, strength="new",
        )

    await relationship_service.add_origin(
        db, edge.id, req.origin_type.value,
    )
    await db.flush()

    return await _edge_to_response(db, edge)


@router.post("/claim", status_code=201)
async def claim_relationship(
    req: RelationshipClaimRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> RelationshipResponse:
    """POST /v1/relationships/claim — Claim relationship by handle/ID/email."""
    from app.core.exceptions import InvalidRequestError

    target = await db.execute(select(Agent).where(Agent.slug == req.claim_value))
    target_agent = target.scalar_one_or_none()
    if not target_agent:
        raise NotFoundError("Agent with this identifier")

    if target_agent.id == current_agent.id:
        raise InvalidRequestError("Cannot claim self")

    edge = await relationship_service.get_or_create_edge(
        db, current_agent.id, target_agent.id, strength="new",
    )
    await relationship_service.add_origin(db, edge.id, "claimed_handle")
    await db.flush()

    return await _edge_to_response(db, edge)


@router.post("/introduce", status_code=201)
async def introduce(
    req: IntroductionRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> IntroductionResponse:
    """POST /v1/relationships/introduce — Request introduction for third party."""
    # Budget enforcement (new accounts get reduced limit of 2/day via NEWBIE_LIMITS)
    await budget_service.check_budget(db, current_agent, "introduction_request")

    intro = await introduction_service.create_introduction(
        db, current_agent, req.target_a_id, req.target_b_id, req.reason,
    )

    await budget_service.increment_budget(db, current_agent, "introduction_request")

    return IntroductionResponse(
        id=intro.id,
        introducer_id=intro.introducer_id,
        target_a_id=intro.target_a_id,
        target_b_id=intro.target_b_id,
        reason=intro.reason,
        status=intro.status,
        expires_at=intro.expires_at,
        created_at=intro.created_at,
    )


@router.post("/introduce/{introduction_id}/accept")
async def accept_introduction(
    introduction_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/relationships/introduce/{id}/accept — Target accepts."""
    intro = await introduction_service.accept_introduction(
        db, introduction_id, current_agent,
    )
    return {"id": introduction_id, "status": intro.status}


@router.post("/introduce/{introduction_id}/decline")
async def decline_introduction(
    introduction_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/relationships/introduce/{id}/decline — Target declines."""
    intro = await introduction_service.decline_introduction(
        db, introduction_id, current_agent,
    )
    return {"id": introduction_id, "status": intro.status}


@router.get("/my")
async def list_relationships(
    strength: str | None = None,
    starred: bool | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/relationships/my — List my relationships."""
    stmt = select(RelationshipEdge).where(
        RelationshipEdge.from_agent_id == current_agent.id,
    )
    if strength:
        stmt = stmt.where(RelationshipEdge.strength == strength)
    if starred is not None:
        stmt = stmt.where(RelationshipEdge.starred == starred)
    if cursor:
        stmt = stmt.where(RelationshipEdge.id > cursor)
    stmt = stmt.order_by(RelationshipEdge.id).limit(limit + 1)

    result = await db.execute(stmt)
    edges = list(result.scalars().all())
    has_more = len(edges) > limit
    if has_more:
        edges = edges[:limit]

    data = [await _edge_to_response(db, e) for e in edges]
    return {
        "data": data,
        "next_cursor": edges[-1].id if has_more else None,
        "has_more": has_more,
    }


@router.get("/{agent_id}")
async def get_relationship(
    agent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/relationships/{agent_id} — Get bidirectional relationship."""
    me_to_them = await relationship_service.get_edge(db, current_agent.id, agent_id)
    them_to_me = await relationship_service.get_edge(db, agent_id, current_agent.id)

    if not me_to_them and not them_to_me:
        raise NotFoundError("Relationship")

    mutual_circles = await relationship_service.get_mutual_circles(
        db, current_agent.id, agent_id,
    )

    response = {
        "me_to_them": await _edge_to_response(db, me_to_them) if me_to_them else None,
        "them_to_me": await _edge_to_response(db, them_to_me) if them_to_me else None,
        "mutual_circles": mutual_circles,
    }
    return response


@router.post("/{agent_id}/block")
async def block_agent(
    agent_id: str,
    req: BlockRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/relationships/{agent_id}/block — Block/unblock Agent."""
    await relationship_service.block_agent(db, current_agent.id, agent_id, req.block)
    await db.flush()
    return {"agent_id": agent_id, "is_blocked": req.block}


@router.put("/{agent_id}/star")
async def star_agent(
    agent_id: str,
    req: StarRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """PUT /v1/relationships/{agent_id}/star — Star/unstar."""
    edge = await relationship_service.get_edge(db, current_agent.id, agent_id)
    if not edge:
        raise NotFoundError("Relationship")

    edge.starred = req.starred
    await db.flush()
    return {"agent_id": agent_id, "starred": req.starred}


async def _edge_to_response(db: AsyncSession, edge: RelationshipEdge) -> RelationshipResponse:
    origins = await relationship_service.get_origins_for_edge(db, edge.id)
    return RelationshipResponse(
        id=edge.id,
        from_agent_id=edge.from_agent_id,
        to_agent_id=edge.to_agent_id,
        strength=edge.strength,
        starred=edge.starred,
        can_direct_task=edge.can_direct_task,
        is_blocked=edge.is_blocked,
        interaction_count=edge.interaction_count,
        success_count=edge.success_count,
        last_interaction_at=edge.last_interaction_at,
        origins=origins,
        created_at=edge.created_at,
    )
