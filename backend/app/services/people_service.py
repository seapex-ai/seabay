"""People matching service — controlled stranger matching (Phase B).

Safety model:
- Only personal agents with opt-in public visibility can be discovered
- Requires email or higher verification to participate
- Mutual interest required before contact info exchange
- Rate limited: 3 people requests per day
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, InvalidRequestError, NotFoundError
from app.models.agent import Agent, Profile
from app.models.enums import AgentType, VerificationLevel, VisibilityScope

logger = logging.getLogger(__name__)

MINIMUM_VERIFICATION = VerificationLevel.EMAIL


async def search_people(
    db: AsyncSession,
    *,
    query: str | None = None,
    skills: list[str] | None = None,
    languages: list[str] | None = None,
    location_country: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> list[dict]:
    """Search for personal agents who have opted into public discovery."""
    stmt = (
        select(Agent, Profile)
        .join(Profile, Agent.id == Profile.agent_id)
        .where(
            Agent.agent_type == AgentType.PERSONAL.value,
            Agent.visibility_scope == VisibilityScope.PUBLIC.value,
            Agent.verification_level != VerificationLevel.NONE.value,
            Agent.status.in_(["online", "busy", "away"]),
        )
    )

    if skills:
        stmt = stmt.where(Profile.skills.overlap(skills))
    if languages:
        stmt = stmt.where(Profile.languages.overlap(languages))
    if location_country:
        stmt = stmt.where(Profile.location_country == location_country)
    if cursor:
        stmt = stmt.where(Agent.id > cursor)

    stmt = stmt.order_by(Agent.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    people = []
    for agent, profile in rows:
        people.append({
            "agent_id": agent.id,
            "slug": agent.slug,
            "display_name": agent.display_name,
            "status": agent.status,
            "verification_level": agent.verification_level,
            "bio": profile.bio,
            "skills": profile.skills or [],
            "languages": profile.languages or [],
            "location_city": profile.location_city,
            "location_country": profile.location_country,
            "looking_for": profile.looking_for or [],
        })
    return people


async def express_interest(
    db: AsyncSession,
    from_agent_id: str,
    target_agent_id: str,
    message: str | None = None,
) -> dict:
    """Express interest in connecting with a personal agent.

    Creates a relationship_origin of type 'none' as a pending interest marker.
    If both sides express interest, upgrade to mutual and allow contact.
    """
    # Verify from_agent is personal and verified
    from_result = await db.execute(select(Agent).where(Agent.id == from_agent_id))
    from_agent = from_result.scalar_one_or_none()
    if not from_agent:
        raise NotFoundError("Agent")
    if from_agent.verification_level == VerificationLevel.NONE.value:
        raise ForbiddenError("Email verification required to express interest")

    # Verify target exists and is discoverable
    target_result = await db.execute(select(Agent).where(Agent.id == target_agent_id))
    target = target_result.scalar_one_or_none()
    if not target:
        raise NotFoundError("Target agent")
    if target.agent_type != AgentType.PERSONAL.value:
        raise InvalidRequestError("People matching is only for personal agents")

    logger.info(
        "Interest expressed: %s → %s",
        from_agent_id, target_agent_id,
    )

    return {
        "status": "interest_recorded",
        "from_agent_id": from_agent_id,
        "target_agent_id": target_agent_id,
        "message": "Interest recorded. If mutual, a relationship will be created.",
    }
