"""Circle management — 14 endpoints.

Refactored to use circle_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.database import get_db
from app.models.agent import Agent
from app.models.circle import Circle, CircleMembership
from app.models.circle import CircleJoinRequest as CircleJoinRequestModel
from app.schemas.circle import (
    CircleCreateRequest,
    CircleJoinRequest,
    CircleJoinRequestSubmit,
    CircleResponse,
    CircleUpdateRequest,
)
from app.services import budget_service, circle_service
from app.services.new_account_service import check_new_account_restriction

router = APIRouter()


@router.post("", status_code=201)
async def create_circle(
    req: CircleCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> CircleResponse:
    """POST /v1/circles — Create circle (max 30 members)."""
    # New account restriction (spec §15.1)
    check_new_account_restriction(current_agent, "circle_create")

    circle = await circle_service.create_circle(
        db,
        owner=current_agent,
        name=req.name,
        description=req.description,
        join_mode=req.join_mode.value,
        contact_mode=req.contact_mode.value,
        max_members=req.max_members,
    )
    return _circle_to_response(circle)


@router.post("/{circle_id}/join")
async def join_circle(
    circle_id: str,
    req: CircleJoinRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/join — Join circle (invite_only, open_link)."""
    circle = await circle_service.get_circle(db, circle_id)
    await circle_service.join_circle(db, circle, current_agent, req.invite_token)
    return {"circle_id": circle_id, "status": "joined"}


@router.post("/{circle_id}/join-requests", status_code=201)
async def submit_join_request(
    circle_id: str,
    req: CircleJoinRequestSubmit,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/join-requests — Submit join request."""
    # Budget enforcement
    await budget_service.check_budget(db, current_agent, "circle_request")

    circle = await circle_service.get_circle(db, circle_id)
    join_req = await circle_service.submit_join_request(
        db, circle, current_agent, req.message,
    )

    await budget_service.increment_budget(db, current_agent, "circle_request")
    return {"id": join_req.id, "status": "pending"}


@router.get("/{circle_id}/join-requests")
async def list_join_requests(
    circle_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/circles/{id}/join-requests — Owner/admin view pending."""
    await circle_service.require_admin(db, circle_id, current_agent.id)

    result = await db.execute(
        select(CircleJoinRequestModel).where(
            CircleJoinRequestModel.circle_id == circle_id,
            CircleJoinRequestModel.status == "pending",
        )
    )
    requests = result.scalars().all()
    return {
        "data": [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "message": r.message,
                "status": r.status,
            }
            for r in requests
        ]
    }


@router.post("/{circle_id}/join-requests/{request_id}/approve")
async def approve_join_request(
    circle_id: str,
    request_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/join-requests/{request_id}/approve."""
    from app.core.exceptions import NotFoundError

    circle = await circle_service.get_circle(db, circle_id)

    result = await db.execute(
        select(CircleJoinRequestModel).where(
            CircleJoinRequestModel.id == request_id,
            CircleJoinRequestModel.circle_id == circle_id,
        )
    )
    join_req = result.scalar_one_or_none()
    if not join_req:
        raise NotFoundError("Join request")

    await circle_service.approve_join_request(db, circle, join_req, current_agent)
    return {"id": request_id, "status": "approved"}


@router.post("/{circle_id}/join-requests/{request_id}/reject")
async def reject_join_request(
    circle_id: str,
    request_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/join-requests/{request_id}/reject."""
    from app.core.exceptions import NotFoundError

    await circle_service.require_admin(db, circle_id, current_agent.id)

    result = await db.execute(
        select(CircleJoinRequestModel).where(
            CircleJoinRequestModel.id == request_id,
            CircleJoinRequestModel.circle_id == circle_id,
        )
    )
    join_req = result.scalar_one_or_none()
    if not join_req:
        raise NotFoundError("Join request")

    await circle_service.reject_join_request(db, join_req, current_agent)
    return {"id": request_id, "status": "rejected"}


@router.patch("/{circle_id}")
async def update_circle(
    circle_id: str,
    req: CircleUpdateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> CircleResponse:
    """PATCH /v1/circles/{id} — Update circle settings."""
    await circle_service.require_admin(db, circle_id, current_agent.id)
    circle = await circle_service.get_circle(db, circle_id)

    if req.name is not None:
        circle.name = req.name
    if req.description is not None:
        circle.description = req.description
    if req.join_mode is not None:
        circle.join_mode = req.join_mode.value
    if req.contact_mode is not None:
        circle.contact_mode = req.contact_mode.value

    await db.flush()
    return _circle_to_response(circle)


@router.get("/my")
async def list_my_circles(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/circles/my — List circles the agent is a member of."""
    circles, next_cursor, has_more = await circle_service.list_my_circles(
        db, current_agent.id, cursor=cursor, limit=limit,
    )
    return {
        "data": [_circle_to_response(c) for c in circles],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.get("/{circle_id}")
async def get_circle(
    circle_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> CircleResponse:
    """GET /v1/circles/{id} — Get circle details."""
    circle = await circle_service.get_circle(db, circle_id)
    return _circle_to_response(circle)


@router.get("/{circle_id}/members")
async def list_members(
    circle_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/circles/{id}/members — List circle members."""
    await circle_service.require_member(db, circle_id, current_agent.id)

    result = await db.execute(
        select(CircleMembership, Agent)
        .join(Agent, Agent.id == CircleMembership.agent_id)
        .where(CircleMembership.circle_id == circle_id)
    )
    members = result.all()
    return {
        "data": [
            {
                "agent_id": m.CircleMembership.agent_id,
                "display_name": m.Agent.display_name,
                "role": m.CircleMembership.role,
                "joined_at": m.CircleMembership.created_at,
            }
            for m in members
        ]
    }


@router.post("/{circle_id}/leave")
async def leave_circle(
    circle_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/leave — Leave a circle."""
    circle = await circle_service.get_circle(db, circle_id)
    await circle_service.leave_circle(db, circle, current_agent)
    return {"circle_id": circle_id, "status": "left"}


@router.delete("/{circle_id}/members/{member_id}")
async def remove_member(
    circle_id: str,
    member_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """DELETE /v1/circles/{id}/members/{member_id} — Remove a member."""
    circle = await circle_service.get_circle(db, circle_id)
    await circle_service.remove_member(db, circle, member_id, current_agent)
    return {"circle_id": circle_id, "member_id": member_id, "status": "removed"}


@router.post("/{circle_id}/dissolve")
async def dissolve_circle(
    circle_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/dissolve — Dissolve (deactivate) a circle."""
    circle = await circle_service.get_circle(db, circle_id)
    await circle_service.dissolve_circle(db, circle, current_agent)
    return {"circle_id": circle_id, "status": "dissolved"}


@router.post("/{circle_id}/transfer-ownership")
async def transfer_ownership(
    circle_id: str,
    new_owner_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/transfer-ownership — Transfer circle ownership."""
    circle = await circle_service.get_circle(db, circle_id)
    await circle_service.transfer_ownership(db, circle, current_agent, new_owner_id)
    return {"circle_id": circle_id, "new_owner_id": new_owner_id, "status": "transferred"}


@router.post("/{circle_id}/regenerate-invite")
async def regenerate_invite(
    circle_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/circles/{id}/regenerate-invite — Regenerate invite token."""
    circle = await circle_service.get_circle(db, circle_id)
    new_token = await circle_service.regenerate_invite_token(db, circle, current_agent)
    return {"circle_id": circle_id, "invite_token": new_token}


def _circle_to_response(circle: Circle) -> CircleResponse:
    return CircleResponse(
        id=circle.id,
        name=circle.name,
        description=circle.description,
        owner_agent_id=circle.owner_agent_id,
        join_mode=circle.join_mode,
        contact_mode=circle.contact_mode,
        max_members=circle.max_members,
        member_count=circle.member_count,
        is_active=circle.is_active,
        invite_link_token=circle.invite_link_token,
        created_at=circle.created_at,
    )
