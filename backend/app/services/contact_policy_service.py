"""Contact policy service — enforces who can task / contact whom.

Implements spec §8 (contact policy enforcement):
- known_direct: only existing relationships can initiate tasks
- circle_intro_only: must share a circle or be introduced
- public_service_only: anyone can task (for service agents)
- request_approval: requires approval before task can proceed

Also enforces introduction_policy:
- open: anyone in network can introduce
- mutual_only: only mutual connections can introduce
- closed: no introductions accepted
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.agent import Agent
from app.models.enums import ContactPolicy, IntroductionPolicy
from app.models.relationship import RelationshipEdge

logger = logging.getLogger(__name__)


async def check_can_task(
    db: AsyncSession,
    from_agent: Agent,
    to_agent: Agent,
) -> None:
    """Verify from_agent is allowed to send a task to to_agent.

    Raises ForbiddenError if contact policy prevents the task.
    """
    policy = to_agent.contact_policy

    # Service agents with public_service_only accept from anyone
    if policy == ContactPolicy.PUBLIC_SERVICE_ONLY.value:
        return

    # Check if there's an existing relationship
    edge = await _get_relationship(db, from_agent.id, to_agent.id)

    if policy == ContactPolicy.KNOWN_DIRECT.value:
        if not edge or edge.is_blocked:
            raise ForbiddenError(
                "This agent only accepts tasks from known contacts. "
                "Establish a relationship first."
            )
        return

    if policy == ContactPolicy.CIRCLE_INTRO_ONLY.value:
        if edge and not edge.is_blocked:
            return

        # Check for shared circles
        has_shared = await _share_circle(db, from_agent.id, to_agent.id)
        if has_shared:
            return

        raise ForbiddenError(
            "This agent only accepts tasks from circle members or "
            "introduced contacts."
        )

    if policy == ContactPolicy.REQUEST_APPROVAL.value:
        # Tasks always allowed but need explicit acceptance
        return

    # Fallback: deny unknown policies
    raise ForbiddenError("Contact not permitted by agent's policy")


async def check_can_introduce(
    db: AsyncSession,
    introducer: Agent,
    target: Agent,
) -> None:
    """Verify introducer is allowed to create an introduction to target.

    Checks target's introduction_policy.
    """
    policy = target.introduction_policy

    if policy == IntroductionPolicy.CLOSED.value:
        raise ForbiddenError(
            "This agent does not accept introductions"
        )

    if policy == IntroductionPolicy.OPEN.value:
        # Check introducer has relationship with target
        edge = await _get_relationship(db, introducer.id, target.id)
        if not edge or edge.is_blocked:
            raise ForbiddenError(
                "You must have a relationship with the target agent "
                "to make introductions"
            )
        return

    if policy == IntroductionPolicy.MUTUAL_ONLY.value:
        # Both directions must exist
        fwd = await _get_relationship(db, introducer.id, target.id)
        rev = await _get_relationship(db, target.id, introducer.id)
        if not fwd or not rev or fwd.is_blocked or rev.is_blocked:
            raise ForbiddenError(
                "This agent only accepts introductions from mutual contacts"
            )
        return

    raise ForbiddenError("Introduction not permitted by agent's policy")


async def check_blocked(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
) -> None:
    """Check if either agent has blocked the other.

    Raises ForbiddenError if blocked in either direction.
    """
    # Check if to_agent blocked from_agent
    edge = await _get_relationship(db, to_agent_id, from_agent_id)
    if edge and edge.is_blocked:
        raise ForbiddenError("You have been blocked by this agent")

    # Check if from_agent blocked to_agent
    edge = await _get_relationship(db, from_agent_id, to_agent_id)
    if edge and edge.is_blocked:
        raise ForbiddenError("You have blocked this agent")


async def get_effective_policy(
    db: AsyncSession,
    agent: Agent,
    requester: Optional[Agent] = None,
) -> dict:
    """Get the effective contact policy for an agent from requester's perspective.

    Returns policy details and whether requester can task.
    """
    result = {
        "contact_policy": agent.contact_policy,
        "introduction_policy": agent.introduction_policy,
        "can_task": False,
        "can_introduce": False,
        "reason": None,
    }

    if not requester:
        result["can_task"] = (
            agent.contact_policy == ContactPolicy.PUBLIC_SERVICE_ONLY.value
        )
        return result

    try:
        await check_can_task(db, requester, agent)
        result["can_task"] = True
    except ForbiddenError as e:
        result["reason"] = str(e)

    try:
        await check_can_introduce(db, requester, agent)
        result["can_introduce"] = True
    except ForbiddenError:
        pass

    return result


async def _get_relationship(
    db: AsyncSession,
    from_id: str,
    to_id: str,
) -> Optional[RelationshipEdge]:
    """Get relationship edge between two agents."""
    result = await db.execute(
        select(RelationshipEdge).where(
            RelationshipEdge.from_agent_id == from_id,
            RelationshipEdge.to_agent_id == to_id,
        )
    )
    return result.scalar_one_or_none()


async def _share_circle(
    db: AsyncSession,
    agent_a_id: str,
    agent_b_id: str,
) -> bool:
    """Check if two agents share any circles."""
    from app.models.circle import CircleMembership

    result = await db.execute(
        select(CircleMembership.circle_id).where(
            CircleMembership.agent_id == agent_a_id,
        ).intersect(
            select(CircleMembership.circle_id).where(
                CircleMembership.agent_id == agent_b_id,
            )
        )
    )
    return result.first() is not None
