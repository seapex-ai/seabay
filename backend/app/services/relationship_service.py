"""Relationship service — contact policy, strength derivation, permission checks.

Covers spec §6 (multi-origin relationships), §7 (forming relationships),
§9.1 (visibility), §10 (contact policy), §14.2 (trust signals).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ContactPolicyDeniedError,
)
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.circle import CircleMembership
from app.models.interaction import Interaction
from app.models.relationship import RelationshipEdge, RelationshipOrigin
from app.models.report import Report


async def get_edge(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
) -> Optional[RelationshipEdge]:
    """Get directional edge between two agents (or None)."""
    result = await db.execute(
        select(RelationshipEdge).where(
            RelationshipEdge.from_agent_id == from_agent_id,
            RelationshipEdge.to_agent_id == to_agent_id,
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_edge(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
    strength: str = "new",
) -> RelationshipEdge:
    """Get or create a directional relationship edge."""
    edge = await get_edge(db, from_agent_id, to_agent_id)
    if not edge:
        edge = RelationshipEdge(
            id=generate_id("relationship_edge"),
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            strength=strength,
        )
        db.add(edge)
        await db.flush()
    return edge


async def add_origin(
    db: AsyncSession,
    edge_id: str,
    origin_type: str,
    source_id: Optional[str] = None,
) -> RelationshipOrigin:
    """Add an origin to a relationship edge (if not already present)."""
    existing = await db.execute(
        select(RelationshipOrigin).where(
            RelationshipOrigin.edge_id == edge_id,
            RelationshipOrigin.origin_type == origin_type,
        )
    )
    if existing.scalar_one_or_none():
        return existing.scalar_one_or_none()

    origin = RelationshipOrigin(
        id=generate_id("relationship_origin"),
        edge_id=edge_id,
        origin_type=origin_type,
        source_id=source_id,
        origin_status="active",
    )
    db.add(origin)
    return origin


async def has_any_relationship(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
) -> bool:
    """Check if there is any non-blocked relationship edge."""
    edge = await get_edge(db, from_agent_id, to_agent_id)
    return edge is not None and not edge.is_blocked


async def has_origin_type(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
    origin_type: str,
) -> bool:
    """Check if a specific origin type exists between two agents."""
    edge = await get_edge(db, from_agent_id, to_agent_id)
    if not edge:
        return False
    result = await db.execute(
        select(RelationshipOrigin).where(
            RelationshipOrigin.edge_id == edge.id,
            RelationshipOrigin.origin_type == origin_type,
            RelationshipOrigin.origin_status == "active",
        )
    )
    return result.scalar_one_or_none() is not None


async def is_blocked(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
) -> bool:
    """Check if from_agent has blocked to_agent."""
    edge = await get_edge(db, from_agent_id, to_agent_id)
    return edge is not None and edge.is_blocked


async def check_contact_allowed(
    db: AsyncSession,
    from_agent: Agent,
    to_agent: Agent,
) -> None:
    """Enforce contact policy per spec §10.1.

    Raises ContactPolicyDeniedError if not allowed.

    Formula (§6.6):
        can_contact = relationship_origin_valid
                      AND target_visibility_allows
                      AND target_contact_policy_allows
                      AND NOT blocked
                      AND under_rate_limit
    """
    # Check if blocked
    if await is_blocked(db, to_agent.id, from_agent.id):
        raise ContactPolicyDeniedError()

    # Check target_visibility_allows (§6.6)
    vis = to_agent.visibility_scope
    if vis == "private":
        raise ContactPolicyDeniedError()
    if vis == "network_only":
        edge = await get_edge(db, to_agent.id, from_agent.id)
        if not edge or edge.is_blocked:
            raise ContactPolicyDeniedError()
    elif vis == "circle_only":
        mutual = await get_mutual_circles(db, to_agent.id, from_agent.id)
        if not mutual:
            raise ContactPolicyDeniedError()
    # vis == "public" → always visible, continue to contact_policy check

    policy = to_agent.contact_policy

    if policy == "closed":
        raise ContactPolicyDeniedError()

    if policy == "public_service_only":
        # Anyone can contact (visibility already checked above)
        return

    if policy == "known_direct":
        # Must have a non-blocked relationship where to_agent knows from_agent
        edge = await get_edge(db, to_agent.id, from_agent.id)
        if not edge or edge.is_blocked:
            raise ContactPolicyDeniedError()
        return

    if policy == "intro_only":
        # Must have been introduced, collaborated, or public_service origin
        edge = await get_edge(db, to_agent.id, from_agent.id)
        if not edge or edge.is_blocked:
            raise ContactPolicyDeniedError()
        # Check for acceptable origins
        result = await db.execute(
            select(RelationshipOrigin).where(
                RelationshipOrigin.edge_id == edge.id,
                RelationshipOrigin.origin_type.in_(["introduced", "collaborated", "public_service"]),
                RelationshipOrigin.origin_status == "active",
            )
        )
        if not result.scalar_one_or_none():
            raise ContactPolicyDeniedError()
        return

    if policy == "circle_request":
        # Must share a circle
        edge = await get_edge(db, to_agent.id, from_agent.id)
        if not edge or edge.is_blocked:
            raise ContactPolicyDeniedError()
        result = await db.execute(
            select(RelationshipOrigin).where(
                RelationshipOrigin.edge_id == edge.id,
                RelationshipOrigin.origin_type == "same_circle",
                RelationshipOrigin.origin_status == "active",
            )
        )
        if not result.scalar_one_or_none():
            raise ContactPolicyDeniedError()
        return


async def derive_strength(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
) -> str:
    """Auto-derive relationship strength per spec §6.5.

    Rules:
    - new: initial state
    - acquaintance: >=1 successful task
    - trusted: >=3 success + 0 reports + avg_rating >= 3.5
    - frequent: mutual star + last_interaction < 30d + >=5 successes
    """
    edge = await get_edge(db, from_agent_id, to_agent_id)
    if not edge:
        return "new"

    success_count = edge.success_count or 0

    if success_count < 1:
        return "new"

    # Check for frequent
    if success_count >= 5 and edge.starred:
        # Check mutual star
        reverse_edge = await get_edge(db, to_agent_id, from_agent_id)
        if reverse_edge and reverse_edge.starred:
            # Check last interaction within 30 days
            if edge.last_interaction_at:
                cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                last_at = edge.last_interaction_at
                if isinstance(last_at, str):
                    last_at = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
                if last_at > cutoff:
                    return "frequent"

    # Check for trusted
    if success_count >= 3:
        # Check report count
        report_result = await db.execute(
            select(func.count()).select_from(Report).where(
                Report.reported_agent_id == to_agent_id,
                Report.reporter_agent_id == from_agent_id,
            )
        )
        report_count = report_result.scalar() or 0
        if report_count == 0:
            # Check avg rating
            rating_result = await db.execute(
                select(func.avg(Interaction.rating_by_from)).where(
                    Interaction.from_agent_id == from_agent_id,
                    Interaction.to_agent_id == to_agent_id,
                    Interaction.rating_by_from.isnot(None),
                )
            )
            avg_rating = rating_result.scalar()
            if avg_rating is None or avg_rating >= 3.5:
                return "trusted"

    return "acquaintance"


async def update_strength(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
) -> Optional[str]:
    """Recalculate and update strength for an edge. Returns new strength or None."""
    edge = await get_edge(db, from_agent_id, to_agent_id)
    if not edge:
        return None

    new_strength = await derive_strength(db, from_agent_id, to_agent_id)
    if edge.strength != new_strength:
        edge.strength = new_strength
    return new_strength


async def record_interaction_on_edge(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
    success: bool,
    rating: Optional[int] = None,
) -> None:
    """Update edge stats after a task interaction."""
    now = datetime.now(timezone.utc)
    for f_id, t_id in [(from_agent_id, to_agent_id), (to_agent_id, from_agent_id)]:
        edge = await get_edge(db, f_id, t_id)
        if edge:
            edge.interaction_count += 1
            if success:
                edge.success_count += 1
            edge.last_interaction_at = now
            if rating and f_id == from_agent_id:
                edge.last_rating = rating


async def add_collaborated_origin(
    db: AsyncSession,
    agent_a_id: str,
    agent_b_id: str,
    task_id: str,
) -> None:
    """Auto-add 'collaborated' origin on first successful task (spec §7)."""
    for from_id, to_id in [(agent_a_id, agent_b_id), (agent_b_id, agent_a_id)]:
        edge = await get_or_create_edge(db, from_id, to_id, strength="acquaintance")

        # Check if 'collaborated' origin already exists
        existing = await db.execute(
            select(RelationshipOrigin).where(
                RelationshipOrigin.edge_id == edge.id,
                RelationshipOrigin.origin_type == "collaborated",
            )
        )
        if not existing.scalar_one_or_none():
            db.add(RelationshipOrigin(
                id=generate_id("relationship_origin"),
                edge_id=edge.id,
                origin_type="collaborated",
                source_id=task_id,
                origin_status="active",
            ))

        # Auto-upgrade strength if still "new"
        if edge.strength == "new":
            edge.strength = "acquaintance"


async def create_circle_edges(
    db: AsyncSession,
    circle_id: str,
    new_agent_id: str,
) -> None:
    """Create same_circle origin edges when a new member joins (spec §8.3)."""
    # Get all existing members
    result = await db.execute(
        select(CircleMembership.agent_id).where(
            CircleMembership.circle_id == circle_id,
            CircleMembership.agent_id != new_agent_id,
        )
    )
    existing_member_ids = [row[0] for row in result.all()]

    for member_id in existing_member_ids:
        # Bidirectional edges
        for from_id, to_id in [(new_agent_id, member_id), (member_id, new_agent_id)]:
            edge = await get_or_create_edge(db, from_id, to_id)
            await add_origin(db, edge.id, "same_circle", source_id=circle_id)


async def block_agent(
    db: AsyncSession,
    blocker_id: str,
    blocked_id: str,
    block: bool = True,
) -> None:
    """Block or unblock an agent. On block, cancel pending tasks."""
    edge = await get_or_create_edge(db, blocker_id, blocked_id)
    edge.is_blocked = block
    if block:
        edge.blocked_at = datetime.now(timezone.utc)


async def get_origins_for_edge(
    db: AsyncSession,
    edge_id: str,
) -> list[dict]:
    """Get all origins for a relationship edge."""
    result = await db.execute(
        select(RelationshipOrigin).where(RelationshipOrigin.edge_id == edge_id)
    )
    return [
        {
            "origin_type": o.origin_type,
            "origin_status": o.origin_status,
            "source_id": o.source_id,
        }
        for o in result.scalars().all()
    ]


async def get_mutual_circles(
    db: AsyncSession,
    agent_a_id: str,
    agent_b_id: str,
) -> list[str]:
    """Get circle IDs where both agents are members."""
    a_circles = select(CircleMembership.circle_id).where(
        CircleMembership.agent_id == agent_a_id
    ).subquery()
    result = await db.execute(
        select(CircleMembership.circle_id).where(
            CircleMembership.agent_id == agent_b_id,
            CircleMembership.circle_id.in_(select(a_circles)),
        )
    )
    return [row[0] for row in result.all()]


async def expire_circle_edges(
    db: AsyncSession,
    circle_id: str,
    agent_id: str,
) -> None:
    """Expire same_circle origins when a member leaves/is removed (spec §8.3).

    Marks the origin_status as 'expired' rather than deleting.
    """
    # Get all same_circle origins involving this agent + circle
    result = await db.execute(
        select(RelationshipOrigin).where(
            RelationshipOrigin.origin_type == "same_circle",
            RelationshipOrigin.source_id == circle_id,
            RelationshipOrigin.origin_status == "active",
        )
    )
    origins = list(result.scalars().all())

    for origin in origins:
        # Get the edge to check if it involves our agent
        edge_result = await db.execute(
            select(RelationshipEdge).where(
                RelationshipEdge.id == origin.edge_id,
            )
        )
        edge = edge_result.scalar_one_or_none()
        if edge and (edge.from_agent_id == agent_id or edge.to_agent_id == agent_id):
            origin.origin_status = "expired"
            origin.expired_at = datetime.now(timezone.utc)

    await db.flush()


async def get_relationship_summary(
    db: AsyncSession,
    agent_id: str,
) -> dict:
    """Get relationship statistics for an agent."""
    # Total relationships
    total_result = await db.execute(
        select(func.count()).select_from(RelationshipEdge).where(
            RelationshipEdge.from_agent_id == agent_id,
            RelationshipEdge.is_blocked.is_(False),
        )
    )
    total = total_result.scalar() or 0

    # By strength
    strength_result = await db.execute(
        select(
            RelationshipEdge.strength,
            func.count(),
        ).where(
            RelationshipEdge.from_agent_id == agent_id,
            RelationshipEdge.is_blocked.is_(False),
        ).group_by(RelationshipEdge.strength)
    )
    by_strength = {row[0]: row[1] for row in strength_result.all()}

    # Starred count
    starred_result = await db.execute(
        select(func.count()).select_from(RelationshipEdge).where(
            RelationshipEdge.from_agent_id == agent_id,
            RelationshipEdge.starred.is_(True),
        )
    )
    starred = starred_result.scalar() or 0

    # Blocked count
    blocked_result = await db.execute(
        select(func.count()).select_from(RelationshipEdge).where(
            RelationshipEdge.from_agent_id == agent_id,
            RelationshipEdge.is_blocked.is_(True),
        )
    )
    blocked = blocked_result.scalar() or 0

    return {
        "total": total,
        "by_strength": by_strength,
        "starred": starred,
        "blocked": blocked,
    }
