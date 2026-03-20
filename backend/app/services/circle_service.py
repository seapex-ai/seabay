"""Circle service — creation, membership, invite tokens, auto-edge creation.

Covers spec §8 (circle system), §8.3 (hard constraints).

V1.5 Hard Constraints:
- max_members <= 30
- default join_mode = invite_only
- default contact_mode = request_only
- Membership != Auto-trust (shared context only)
- On join: auto-create same_circle origin edges to all existing members
"""

from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.circle import Circle, CircleJoinRequest, CircleMembership
from app.services import relationship_service


async def create_circle(
    db: AsyncSession,
    owner: Agent,
    name: str,
    description: Optional[str] = None,
    join_mode: str = "invite_only",
    contact_mode: str = "request_only",
    max_members: int = 30,
) -> Circle:
    """Create a new circle with owner as first member."""
    max_members = min(max_members, settings.CIRCLE_MAX_MEMBERS)

    circle_id = generate_id("circle")
    invite_token = secrets.token_urlsafe(32)

    circle = Circle(
        id=circle_id,
        name=name,
        description=description,
        owner_agent_id=owner.id,
        join_mode=join_mode,
        contact_mode=contact_mode,
        max_members=max_members,
        invite_link_token=invite_token,
        member_count=1,
    )
    db.add(circle)

    # Add owner as member
    db.add(CircleMembership(
        id=generate_id("circle_membership"),
        circle_id=circle_id,
        agent_id=owner.id,
        role="owner",
    ))

    await db.flush()
    return circle


async def join_circle(
    db: AsyncSession,
    circle: Circle,
    agent: Agent,
    invite_token: Optional[str] = None,
) -> None:
    """Join a circle. Validates membership, capacity, and token."""
    # Check already a member
    existing = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle.id,
            CircleMembership.agent_id == agent.id,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(message="Already a member")

    if circle.member_count >= circle.max_members:
        raise InvalidRequestError("Circle is full")

    # Validate by join_mode
    if circle.join_mode == "invite_only":
        if not invite_token or invite_token != circle.invite_link_token:
            raise ForbiddenError(message="Invalid invite token")
    elif circle.join_mode == "open_link":
        if not invite_token or invite_token != circle.invite_link_token:
            raise ForbiddenError(message="Invalid link token")
    elif circle.join_mode == "request_approve":
        raise InvalidRequestError("Use /join-requests endpoint for request_approve circles")

    # Add member
    db.add(CircleMembership(
        id=generate_id("circle_membership"),
        circle_id=circle.id,
        agent_id=agent.id,
        role="member",
    ))
    circle.member_count += 1

    # Auto-create same_circle origin edges to all existing members (spec §8.3)
    await relationship_service.create_circle_edges(db, circle.id, agent.id)

    await db.flush()


async def submit_join_request(
    db: AsyncSession,
    circle: Circle,
    agent: Agent,
    message: Optional[str] = None,
) -> CircleJoinRequest:
    """Submit a join request for request_approve circles."""
    if circle.join_mode != "request_approve":
        raise InvalidRequestError("Circle does not accept join requests")

    # Check for existing pending request
    existing = await db.execute(
        select(CircleJoinRequest).where(
            CircleJoinRequest.circle_id == circle.id,
            CircleJoinRequest.agent_id == agent.id,
            CircleJoinRequest.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(message="You already have a pending join request")

    request = CircleJoinRequest(
        id=generate_id("circle_join_request"),
        circle_id=circle.id,
        agent_id=agent.id,
        message=message,
    )
    db.add(request)
    await db.flush()
    return request


async def approve_join_request(
    db: AsyncSession,
    circle: Circle,
    request: CircleJoinRequest,
    approver: Agent,
) -> None:
    """Approve a join request and add the agent as a member."""
    await require_admin(db, circle.id, approver.id)

    if circle.member_count >= circle.max_members:
        raise InvalidRequestError("Circle is full")

    if request.status != "pending":
        raise InvalidRequestError(f"Join request is {request.status}")

    request.status = "approved"
    request.reviewed_by = approver.id

    db.add(CircleMembership(
        id=generate_id("circle_membership"),
        circle_id=circle.id,
        agent_id=request.agent_id,
        role="member",
    ))
    circle.member_count += 1

    # Auto-create same_circle origin edges
    await relationship_service.create_circle_edges(db, circle.id, request.agent_id)

    await db.flush()


async def reject_join_request(
    db: AsyncSession,
    request: CircleJoinRequest,
    rejector: Agent,
) -> None:
    """Reject a join request."""
    if request.status != "pending":
        raise InvalidRequestError(f"Join request is {request.status}")

    request.status = "rejected"
    request.reviewed_by = rejector.id
    await db.flush()


async def get_circle(db: AsyncSession, circle_id: str) -> Circle:
    """Get circle by ID or raise NotFoundError."""
    result = await db.execute(select(Circle).where(Circle.id == circle_id))
    circle = result.scalar_one_or_none()
    if not circle:
        raise NotFoundError("Circle")
    return circle


async def require_admin(db: AsyncSession, circle_id: str, agent_id: str) -> None:
    """Check that agent is circle owner or admin."""
    result = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle_id,
            CircleMembership.agent_id == agent_id,
            CircleMembership.role.in_(["owner", "admin"]),
        )
    )
    if not result.scalar_one_or_none():
        raise ForbiddenError(message="Must be circle owner or admin")


async def require_member(db: AsyncSession, circle_id: str, agent_id: str) -> None:
    """Check that agent is a circle member."""
    result = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle_id,
            CircleMembership.agent_id == agent_id,
        )
    )
    if not result.scalar_one_or_none():
        raise ForbiddenError(message="Must be a circle member")


async def remove_member(
    db: AsyncSession,
    circle: Circle,
    member_agent_id: str,
    remover: Agent,
) -> None:
    """Remove a member from the circle.

    Only circle owner/admin can remove members.
    Owner cannot be removed.
    On removal: mark same_circle origins as expired.
    """
    await require_admin(db, circle.id, remover.id)

    # Cannot remove the owner
    if member_agent_id == circle.owner_agent_id:
        raise InvalidRequestError("Cannot remove the circle owner")

    # Find the membership
    result = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle.id,
            CircleMembership.agent_id == member_agent_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise NotFoundError("Member")

    # Remove membership
    await db.delete(membership)
    circle.member_count = max(0, circle.member_count - 1)

    # Expire same_circle origin edges (spec §8.3)
    await relationship_service.expire_circle_edges(db, circle.id, member_agent_id)

    await db.flush()


async def leave_circle(
    db: AsyncSession,
    circle: Circle,
    agent: Agent,
) -> None:
    """Agent voluntarily leaves a circle.

    Owner cannot leave (must transfer ownership or dissolve).
    """
    if agent.id == circle.owner_agent_id:
        raise InvalidRequestError(
            "Owner cannot leave. Transfer ownership or dissolve the circle."
        )

    result = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle.id,
            CircleMembership.agent_id == agent.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise NotFoundError("Membership")

    await db.delete(membership)
    circle.member_count = max(0, circle.member_count - 1)

    # Expire same_circle origin edges
    await relationship_service.expire_circle_edges(db, circle.id, agent.id)

    await db.flush()


async def dissolve_circle(
    db: AsyncSession,
    circle: Circle,
    owner: Agent,
) -> None:
    """Dissolve (deactivate) a circle. Owner-only.

    Does NOT delete the circle, but marks it as inactive.
    All memberships are removed, all same_circle origins expired.
    """
    if owner.id != circle.owner_agent_id:
        raise ForbiddenError(message="Only the circle owner can dissolve it")

    # Get all members before dissolving
    result = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle.id,
        )
    )
    memberships = list(result.scalars().all())

    # Expire all same_circle origins for all members
    for membership in memberships:
        await relationship_service.expire_circle_edges(
            db, circle.id, membership.agent_id,
        )
        await db.delete(membership)

    circle.is_active = False
    circle.member_count = 0

    await db.flush()


async def transfer_ownership(
    db: AsyncSession,
    circle: Circle,
    current_owner: Agent,
    new_owner_id: str,
) -> None:
    """Transfer circle ownership to another member."""
    if current_owner.id != circle.owner_agent_id:
        raise ForbiddenError(message="Only the circle owner can transfer ownership")

    # Verify new owner is a member
    result = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle.id,
            CircleMembership.agent_id == new_owner_id,
        )
    )
    new_owner_membership = result.scalar_one_or_none()
    if not new_owner_membership:
        raise InvalidRequestError("New owner must be a circle member")

    # Update roles
    old_owner_result = await db.execute(
        select(CircleMembership).where(
            CircleMembership.circle_id == circle.id,
            CircleMembership.agent_id == current_owner.id,
        )
    )
    old_owner_membership = old_owner_result.scalar_one_or_none()
    if old_owner_membership:
        old_owner_membership.role = "admin"  # demote to admin

    new_owner_membership.role = "owner"
    circle.owner_agent_id = new_owner_id

    await db.flush()


async def list_my_circles(
    db: AsyncSession,
    agent_id: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> tuple[list[Circle], Optional[str], bool]:
    """List circles the agent is a member of."""
    stmt = (
        select(Circle)
        .join(CircleMembership, CircleMembership.circle_id == Circle.id)
        .where(
            CircleMembership.agent_id == agent_id,
            Circle.is_active.is_(True),
        )
    )

    if cursor:
        stmt = stmt.where(Circle.id > cursor)

    stmt = stmt.order_by(Circle.id).limit(limit + 1)
    result = await db.execute(stmt)
    circles = list(result.scalars().all())

    has_more = len(circles) > limit
    if has_more:
        circles = circles[:limit]

    next_cursor = circles[-1].id if has_more else None
    return circles, next_cursor, has_more


async def regenerate_invite_token(
    db: AsyncSession,
    circle: Circle,
    admin: Agent,
) -> str:
    """Regenerate the circle invite token. Admin-only."""
    await require_admin(db, circle.id, admin.id)
    circle.invite_link_token = secrets.token_urlsafe(32)
    await db.flush()
    return circle.invite_link_token
