"""Visibility service — field-level profile visibility enforcement.

Implements spec §9.2 (profile field visibility):
- Service agents: all fields public by default
- Personal agents: configurable per-field visibility
- Access levels: public < network < circle < self
- looking_for: always forced private for personal agents

Visibility determines which fields a viewer can see based on their
relationship to the agent.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, Profile, ProfileFieldVisibility
from app.models.enums import AgentType

logger = logging.getLogger(__name__)

# Default field visibility for personal agents (spec §9.2)
PERSONAL_DEFAULTS: dict[str, str] = {
    "display_name": "network_only",
    "bio": "network_only",
    "skills": "network_only",
    "risk_capabilities": "network_only",
    "interests": "network_only",
    "languages": "network_only",
    "location_city": "private",
    "location_country": "private",
    "timezone": "private",
    "can_offer": "network_only",
    "looking_for": "private",       # forced — never public
    "pricing_hint": "network_only",
    "homepage_url": "network_only",
}

# Fields that can never be made public for personal agents
FORCED_PRIVATE_FIELDS = {"looking_for"}

# Access level hierarchy (lower = more accessible)
ACCESS_LEVELS = {
    "public": 0,
    "network_only": 1,
    "circle_only": 2,
    "private": 3,
}

VIEWER_LEVELS = {
    "public": 0,
    "network": 1,
    "circle": 2,
    "self": 3,
}


async def get_visible_profile(
    db: AsyncSession,
    agent: Agent,
    viewer: Optional[Agent] = None,
) -> dict:
    """Get agent profile filtered by viewer's access level.

    Returns only the fields the viewer is authorized to see.
    """
    if not agent.profile:
        return {}

    profile = agent.profile

    # Service agents: everything is public
    if agent.agent_type == AgentType.SERVICE.value:
        return _profile_to_dict(profile)

    # Self-view: return everything
    if viewer and viewer.id == agent.id:
        return _profile_to_dict(profile)

    # Get field visibility overrides
    field_vis = await _get_field_visibility_map(db, agent.id)

    # Determine viewer's access level
    access_level = await _determine_access_level(db, agent.id, viewer)

    # Filter fields based on visibility
    all_fields = _profile_to_dict(profile)
    filtered = {}

    for field_name, value in all_fields.items():
        # Get effective visibility for this field
        vis = field_vis.get(field_name, PERSONAL_DEFAULTS.get(field_name, "private"))
        if _can_see(vis, access_level):
            filtered[field_name] = value

    return filtered


async def get_public_profile(
    db: AsyncSession,
    agent: Agent,
) -> dict:
    """Get profile visible to unauthenticated users.

    Service agents: full profile.
    Personal agents: only explicitly public fields.
    """
    return await get_visible_profile(db, agent, viewer=None)


async def validate_visibility_update(
    agent: Agent,
    field_name: str,
    visibility: str,
) -> str:
    """Validate a visibility update request.

    Enforces:
    - looking_for can never be public for personal agents
    - Valid visibility values only
    - Returns the validated visibility value
    """
    if visibility not in ACCESS_LEVELS:
        raise ValueError(f"Invalid visibility: {visibility}")

    if agent.agent_type == AgentType.PERSONAL.value:
        if field_name in FORCED_PRIVATE_FIELDS and visibility != "private":
            raise ValueError(
                f"Field '{field_name}' must remain private for personal agents"
            )

    return visibility


async def get_agent_card_for_viewer(
    db: AsyncSession,
    agent: Agent,
    viewer: Optional[Agent] = None,
) -> dict:
    """Build a complete agent card with visibility-filtered profile.

    Used by GET /v1/agents/{id} and relationship endpoints.
    """
    profile_data = await get_visible_profile(db, agent, viewer)

    badges = []
    if agent.verification_level != "none":
        badges.append(agent.verification_level)

    return {
        "id": agent.id,
        "slug": agent.slug,
        "display_name": agent.display_name,
        "agent_type": agent.agent_type,
        "owner_type": agent.owner_type,
        "verification_level": agent.verification_level,
        "visibility_scope": agent.visibility_scope,
        "contact_policy": agent.contact_policy,
        "introduction_policy": agent.introduction_policy,
        "status": agent.status,
        "last_seen_at": agent.last_seen_at,
        "profile": profile_data,
        "badges": badges,
        "region": agent.region,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


async def _get_field_visibility_map(
    db: AsyncSession,
    agent_id: str,
) -> dict[str, str]:
    """Load field visibility settings for an agent."""
    result = await db.execute(
        select(ProfileFieldVisibility).where(
            ProfileFieldVisibility.agent_id == agent_id,
        )
    )
    return {v.field_name: v.visibility for v in result.scalars().all()}


async def _determine_access_level(
    db: AsyncSession,
    agent_id: str,
    viewer: Optional[Agent],
) -> str:
    """Determine the viewer's access level relative to the agent."""
    if not viewer:
        return "public"

    if viewer.id == agent_id:
        return "self"

    from app.services import relationship_service

    # Check if they have a relationship
    edge = await relationship_service.get_edge(db, agent_id, viewer.id)
    if edge and not edge.is_blocked:
        # Check for mutual circles
        mutual = await relationship_service.get_mutual_circles(
            db, agent_id, viewer.id,
        )
        if mutual:
            return "circle"
        return "network"

    return "public"


def _can_see(field_vis: str, viewer_level: str) -> bool:
    """Check if viewer_level can see a field with given visibility."""
    return VIEWER_LEVELS.get(viewer_level, 0) >= ACCESS_LEVELS.get(field_vis, 3)


def _profile_to_dict(profile: Profile) -> dict:
    """Convert profile to dict."""
    return {
        "bio": profile.bio,
        "skills": profile.skills or [],
        "risk_capabilities": profile.risk_capabilities or [],
        "interests": profile.interests or [],
        "languages": profile.languages or [],
        "location_city": profile.location_city,
        "location_country": profile.location_country,
        "timezone": profile.timezone,
        "can_offer": profile.can_offer or [],
        "looking_for": profile.looking_for or [],
        "pricing_hint": profile.pricing_hint,
        "homepage_url": profile.homepage_url,
    }
