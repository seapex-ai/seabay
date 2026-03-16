"""Introduction service — mutual introduction protocol.

Covers spec §2.3-2.4 (mutual intro flow), §7.4 (forming relationships via introduction).

Flow:
1. Introducer calls POST /v1/relationships/introduce with both targets
2. Both targets get notifications
3. Status: pending → a_accepted / b_accepted → both_accepted
4. On both_accepted: auto-create origin_type=introduced edges
5. Expires in 72h if not both accepted
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.introduction import Introduction
from app.services import relationship_service


async def create_introduction(
    db: AsyncSession,
    introducer: Agent,
    target_a_id: str,
    target_b_id: str,
    reason: Optional[str] = None,
) -> Introduction:
    """Create a new introduction.

    Requirements:
    - Introducer has relationship with both targets
    - Both targets' introduction_policy != closed
    """
    if target_a_id == target_b_id:
        raise InvalidRequestError("Cannot introduce an agent to themselves")
    if target_a_id == introducer.id or target_b_id == introducer.id:
        raise InvalidRequestError("Cannot include yourself in an introduction")

    # Verify both targets exist
    for agent_id in [target_a_id, target_b_id]:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        target = result.scalar_one_or_none()
        if not target:
            raise NotFoundError(f"Agent {agent_id}")
        if target.introduction_policy == "closed":
            raise InvalidRequestError(
                f"Agent {agent_id} does not accept introductions"
            )

    # Verify introducer has relationships with both
    for target_id in [target_a_id, target_b_id]:
        has_rel = await relationship_service.has_any_relationship(
            db, introducer.id, target_id,
        )
        if not has_rel:
            raise InvalidRequestError(
                f"No active relationship with {target_id}"
            )

    # Check for existing pending introduction
    existing = await db.execute(
        select(Introduction).where(
            Introduction.introducer_id == introducer.id,
            Introduction.status.in_(["pending", "a_accepted", "b_accepted"]),
        ).where(
            (
                (Introduction.target_a_id == target_a_id)
                & (Introduction.target_b_id == target_b_id)
            )
            | (
                (Introduction.target_a_id == target_b_id)
                & (Introduction.target_b_id == target_a_id)
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(message="Introduction already pending between these agents")

    now = datetime.now(timezone.utc)
    ttl = settings.INTRODUCTION_TTL_HOURS

    intro = Introduction(
        id=generate_id("introduction"),
        introducer_id=introducer.id,
        target_a_id=target_a_id,
        target_b_id=target_b_id,
        reason=reason,
        status="pending",
        ttl_seconds=ttl * 3600,
        expires_at=now + timedelta(hours=ttl),
    )
    db.add(intro)
    await db.flush()
    return intro


async def accept_introduction(
    db: AsyncSession,
    introduction_id: str,
    agent: Agent,
) -> Introduction:
    """Accept an introduction. When both accept, auto-create edges."""
    result = await db.execute(
        select(Introduction).where(Introduction.id == introduction_id)
    )
    intro = result.scalar_one_or_none()
    if not intro:
        raise NotFoundError("Introduction")

    if agent.id not in (intro.target_a_id, intro.target_b_id):
        raise InvalidRequestError("You are not a target of this introduction")

    if intro.status in ("declined", "expired", "cancelled", "both_accepted"):
        raise ConflictError(message=f"Introduction is {intro.status}")

    # Check expiry
    now = datetime.now(timezone.utc)
    if intro.expires_at and now > intro.expires_at:
        intro.status = "expired"
        await db.flush()
        raise ConflictError(message="Introduction has expired")

    # Update status
    if agent.id == intro.target_a_id:
        intro.a_responded_at = now
        if intro.status == "b_accepted":
            intro.status = "both_accepted"
        else:
            intro.status = "a_accepted"
    else:
        intro.b_responded_at = now
        if intro.status == "a_accepted":
            intro.status = "both_accepted"
        else:
            intro.status = "b_accepted"

    # If both accepted, create bidirectional edges
    if intro.status == "both_accepted":
        await _create_introduction_edges(db, intro)

    await db.flush()
    return intro


async def decline_introduction(
    db: AsyncSession,
    introduction_id: str,
    agent: Agent,
) -> Introduction:
    """Decline an introduction."""
    result = await db.execute(
        select(Introduction).where(Introduction.id == introduction_id)
    )
    intro = result.scalar_one_or_none()
    if not intro:
        raise NotFoundError("Introduction")

    if agent.id not in (intro.target_a_id, intro.target_b_id):
        raise InvalidRequestError("You are not a target of this introduction")

    if intro.status in ("both_accepted", "declined", "expired", "cancelled"):
        raise ConflictError(message=f"Introduction is {intro.status}")

    now = datetime.now(timezone.utc)
    intro.status = "declined"
    if agent.id == intro.target_a_id:
        intro.a_responded_at = now
    else:
        intro.b_responded_at = now

    await db.flush()
    return intro


async def _create_introduction_edges(
    db: AsyncSession,
    intro: Introduction,
) -> None:
    """Create bidirectional relationship edges when both parties accept."""
    for from_id, to_id in [
        (intro.target_a_id, intro.target_b_id),
        (intro.target_b_id, intro.target_a_id),
    ]:
        edge = await relationship_service.get_or_create_edge(
            db, from_id, to_id, strength="new",
        )
        await relationship_service.add_origin(
            db, edge.id, "introduced", source_id=intro.id,
        )
