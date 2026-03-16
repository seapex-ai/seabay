"""Agent service — registration, profile management, visibility filtering, status.

Covers spec §5 (agent registration), §9 (visibility & profile),
§14.4 (verification levels), §15.1 (agent status).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.core.security import extract_key_prefix, generate_api_key, hash_api_key
from app.models.agent import Agent, Profile, ProfileFieldVisibility
from app.models.enums import (
    VERIFICATION_WEIGHTS,
    AgentType,
    ContactPolicy,
    VerificationLevel,
    VisibilityScope,
)
from app.models.verification import Verification

# Protected brand words that cannot be used in display_name (spec §5.3)
PROTECTED_BRAND_WORDS = {
    "openai", "chatgpt", "gpt", "anthropic", "claude", "google", "gemini",
    "meta", "llama", "microsoft", "copilot", "amazon", "alexa", "apple",
    "siri", "baidu", "ernie", "bytedance", "doubao", "grok", "xai",
    "seabay",
}


def check_protected_brand(display_name: str) -> None:
    """Check display_name against protected brand words."""
    name_lower = display_name.lower()
    for brand in PROTECTED_BRAND_WORDS:
        if brand in name_lower:
            raise InvalidRequestError(
                f"Display name contains protected brand word: {brand}"
            )


async def register_agent(
    db: AsyncSession,
    slug: str,
    display_name: str,
    agent_type: AgentType = AgentType.PERSONAL,
    owner_type: str = "individual",
    runtime: Optional[str] = None,
    endpoint: Optional[str] = None,
    bio: Optional[str] = None,
    skills: Optional[list] = None,
    languages: Optional[list] = None,
    location_city: Optional[str] = None,
    location_country: Optional[str] = None,
) -> tuple[Agent, str]:
    """Register a new agent. Returns (agent, api_key).

    The api_key is returned only at registration and never stored in plaintext.
    """
    # Check slug uniqueness
    existing = await db.execute(select(Agent).where(Agent.slug == slug))
    if existing.scalar_one_or_none():
        raise ConflictError(message=f"Slug '{slug}' is already taken")

    # Check protected brand words
    check_protected_brand(display_name)

    # Set defaults based on agent_type
    if agent_type == AgentType.SERVICE:
        default_visibility = VisibilityScope.PUBLIC.value
        default_contact = ContactPolicy.PUBLIC_SERVICE_ONLY.value
    else:
        default_visibility = VisibilityScope.NETWORK_ONLY.value
        default_contact = ContactPolicy.KNOWN_DIRECT.value

    # Generate API key
    api_key = generate_api_key()
    api_key_hashed = hash_api_key(api_key)

    agent_id = generate_id("agent")
    agent = Agent(
        id=agent_id,
        slug=slug,
        display_name=display_name,
        agent_type=agent_type.value,
        owner_type=owner_type,
        runtime=runtime,
        endpoint=endpoint,
        api_key_hash=api_key_hashed,
        api_key_prefix=extract_key_prefix(api_key),
        visibility_scope=default_visibility,
        contact_policy=default_contact,
        status="offline",
    )
    db.add(agent)

    # Create profile
    profile = Profile(
        id=generate_id("profile"),
        agent_id=agent_id,
        bio=bio,
        skills=skills or [],
        languages=languages or [],
        location_city=location_city,
        location_country=location_country,
    )
    db.add(profile)

    await db.flush()
    await db.refresh(agent)
    await db.refresh(agent, ["profile"])
    return agent, api_key


async def update_agent(
    db: AsyncSession,
    agent: Agent,
    **kwargs,
) -> Agent:
    """Update agent fields. Only non-None values are updated."""
    # Ensure profile is loaded (avoid lazy-load in async context)
    await db.refresh(agent, ["profile"])

    # Agent-level fields
    agent_fields = {
        "display_name", "status", "endpoint", "visibility_scope",
        "contact_policy", "introduction_policy",
    }
    for field in agent_fields:
        value = kwargs.get(field)
        if value is not None:
            if field in ("visibility_scope", "contact_policy", "introduction_policy"):
                value = value.value if hasattr(value, "value") else value

            # Personal agents cannot set visibility_scope=public (requires eligibility gate)
            if field == "visibility_scope" and value == "public":
                if agent.agent_type == AgentType.PERSONAL.value:
                    raise InvalidRequestError(
                        "Personal agents cannot set visibility_scope to public"
                    )

            # public_service_only contact policy is only valid for service agents
            if field == "contact_policy" and value == ContactPolicy.PUBLIC_SERVICE_ONLY.value:
                if agent.agent_type == AgentType.PERSONAL.value:
                    raise InvalidRequestError(
                        "Personal agents cannot use public_service_only contact policy"
                    )

            setattr(agent, field, value)

    # Profile fields
    profile_fields = {
        "bio", "skills", "risk_capabilities", "interests", "languages",
        "location_city", "location_country", "timezone",
        "can_offer", "looking_for", "pricing_hint", "homepage_url",
    }
    if agent.profile:
        for field in profile_fields:
            value = kwargs.get(field)
            if value is not None:
                setattr(agent.profile, field, value)

    # Field visibility
    field_visibility = kwargs.get("field_visibility")
    if field_visibility:
        from app.services.visibility_service import validate_visibility_update

        for field_name, vis in field_visibility.items():
            # Validate before saving — enforces FORCED_PRIVATE_FIELDS for personal agents
            validated_vis = await validate_visibility_update(agent, field_name, vis)

            result = await db.execute(
                select(ProfileFieldVisibility).where(
                    ProfileFieldVisibility.agent_id == agent.id,
                    ProfileFieldVisibility.field_name == field_name,
                )
            )
            pfv = result.scalar_one_or_none()
            if pfv:
                pfv.visibility = validated_vis
            else:
                db.add(ProfileFieldVisibility(
                    id=generate_id("profile_field_visibility"),
                    agent_id=agent.id,
                    field_name=field_name,
                    visibility=validated_vis,
                ))

    await db.flush()
    await db.refresh(agent)
    await db.refresh(agent, ["profile"])
    return agent


async def get_agent(db: AsyncSession, agent_id: str) -> Agent:
    """Get agent by ID or raise NotFoundError."""
    result = await db.execute(
        select(Agent).options(selectinload(Agent.profile)).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent")
    return agent


async def get_agent_by_slug(db: AsyncSession, slug: str) -> Agent:
    """Get agent by slug or raise NotFoundError."""
    result = await db.execute(
        select(Agent).options(selectinload(Agent.profile)).where(Agent.slug == slug)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent")
    return agent


async def filter_profile_by_visibility(
    db: AsyncSession,
    agent: Agent,
    viewer: Optional[Agent] = None,
) -> dict:
    """Filter agent profile fields based on visibility settings (spec §9.2).

    Returns only fields the viewer is allowed to see.
    """
    if not agent.profile:
        return {}

    profile = agent.profile

    # Self-view: return everything
    if viewer and viewer.id == agent.id:
        return _profile_to_dict(profile)

    # Get field visibility settings
    vis_result = await db.execute(
        select(ProfileFieldVisibility).where(
            ProfileFieldVisibility.agent_id == agent.id,
        )
    )
    field_vis = {v.field_name: v.visibility for v in vis_result.scalars().all()}

    # Determine viewer's access level
    access_level = "public"  # default for unauthenticated
    if viewer:
        from app.services import relationship_service
        edge = await relationship_service.get_edge(db, agent.id, viewer.id)
        if edge and not edge.is_blocked:
            access_level = "network"
            # Check for circle membership
            mutual = await relationship_service.get_mutual_circles(db, agent.id, viewer.id)
            if mutual:
                access_level = "circle"

    # Filter fields
    filtered = {}
    all_fields = _profile_to_dict(profile)
    for field_name, value in all_fields.items():
        vis = field_vis.get(field_name, agent.visibility_scope)
        if _can_see(vis, access_level):
            filtered[field_name] = value

    return filtered


def _can_see(field_vis: str, viewer_level: str) -> bool:
    """Check if viewer_level can see a field with given visibility."""
    levels = {"public": 0, "network_only": 1, "circle_only": 2, "private": 3}
    viewer_levels = {"public": 0, "network": 1, "circle": 2, "self": 3}
    return viewer_levels.get(viewer_level, 0) >= levels.get(field_vis, 3)


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


async def delete_agent(db: AsyncSession, agent_id: str) -> None:
    """Delete agent and all associated data (GDPR right to erasure).

    Cascade deletes profile + field_visibilities via ORM cascade.
    Manually deletes all other related records.
    """
    from app.models.circle import Circle, CircleJoinRequest, CircleMembership
    from app.models.intent import Intent
    from app.models.interaction import Interaction
    from app.models.introduction import Introduction
    from app.models.metrics import PopularityMetricsDaily, TrustMetricsDaily
    from app.models.rate_limit_budget import RateLimitBudget
    from app.models.relationship import RelationshipEdge, RelationshipOrigin
    from app.models.report import Report
    from app.models.task import HumanConfirmSession, Task

    agent = await get_agent(db, agent_id)

    # Delete human confirm sessions for tasks involving this agent
    task_ids_stmt = select(Task.id).where(
        (Task.from_agent_id == agent_id) | (Task.to_agent_id == agent_id)
    )
    await db.execute(
        delete(HumanConfirmSession).where(
            HumanConfirmSession.task_id.in_(task_ids_stmt)
        )
    )

    # Delete relationship origins for edges involving this agent
    edge_ids_stmt = select(RelationshipEdge.id).where(
        (RelationshipEdge.from_agent_id == agent_id)
        | (RelationshipEdge.to_agent_id == agent_id)
    )
    await db.execute(
        delete(RelationshipOrigin).where(
            RelationshipOrigin.edge_id.in_(edge_ids_stmt)
        )
    )

    # Delete records referencing agent_id (both directions where applicable)
    await db.execute(delete(RelationshipEdge).where(
        (RelationshipEdge.from_agent_id == agent_id)
        | (RelationshipEdge.to_agent_id == agent_id)
    ))
    await db.execute(delete(Interaction).where(
        (Interaction.from_agent_id == agent_id)
        | (Interaction.to_agent_id == agent_id)
    ))
    await db.execute(delete(Task).where(
        (Task.from_agent_id == agent_id) | (Task.to_agent_id == agent_id)
    ))
    await db.execute(delete(Introduction).where(
        (Introduction.introducer_id == agent_id)
        | (Introduction.target_a_id == agent_id)
        | (Introduction.target_b_id == agent_id)
    ))
    await db.execute(delete(Intent).where(Intent.from_agent_id == agent_id))
    await db.execute(delete(CircleJoinRequest).where(
        CircleJoinRequest.agent_id == agent_id
    ))
    await db.execute(delete(CircleMembership).where(
        CircleMembership.agent_id == agent_id
    ))
    await db.execute(delete(Circle).where(Circle.owner_agent_id == agent_id))
    await db.execute(delete(Report).where(
        (Report.reporter_agent_id == agent_id)
        | (Report.reported_agent_id == agent_id)
    ))
    await db.execute(delete(Verification).where(
        Verification.agent_id == agent_id
    ))
    await db.execute(delete(RateLimitBudget).where(
        RateLimitBudget.agent_id == agent_id
    ))
    await db.execute(delete(TrustMetricsDaily).where(
        TrustMetricsDaily.agent_id == agent_id
    ))
    await db.execute(delete(PopularityMetricsDaily).where(
        PopularityMetricsDaily.agent_id == agent_id
    ))

    # Delete agent (cascade handles profile + field_visibilities)
    await db.delete(agent)
    await db.flush()


async def export_agent_data(db: AsyncSession, agent_id: str) -> dict:
    """Export all agent data for GDPR data portability.

    Returns a JSON-serializable dict containing all data associated
    with the agent across all tables.
    """
    from app.models.circle import CircleMembership
    from app.models.intent import Intent
    from app.models.interaction import Interaction
    from app.models.relationship import RelationshipEdge
    from app.models.task import Task

    agent = await get_agent(db, agent_id)

    # Profile
    profile_data = _profile_to_dict(agent.profile) if agent.profile else {}

    # Field visibilities
    fv_result = await db.execute(
        select(ProfileFieldVisibility).where(
            ProfileFieldVisibility.agent_id == agent_id
        )
    )
    field_vis = [
        {"field_name": v.field_name, "visibility": v.visibility}
        for v in fv_result.scalars().all()
    ]

    # Relationships (outgoing)
    rel_result = await db.execute(
        select(RelationshipEdge).where(
            (RelationshipEdge.from_agent_id == agent_id)
            | (RelationshipEdge.to_agent_id == agent_id)
        )
    )
    relationships = [
        {
            "from_agent_id": r.from_agent_id,
            "to_agent_id": r.to_agent_id,
            "strength": r.strength,
            "is_blocked": r.is_blocked,
            "created_at": str(r.created_at),
        }
        for r in rel_result.scalars().all()
    ]

    # Tasks
    task_result = await db.execute(
        select(Task).where(
            (Task.from_agent_id == agent_id)
            | (Task.to_agent_id == agent_id)
        )
    )
    tasks = [
        {
            "id": t.id,
            "from_agent_id": t.from_agent_id,
            "to_agent_id": t.to_agent_id,
            "task_type": t.task_type,
            "description": t.description,
            "status": t.status,
            "risk_level": t.risk_level,
            "created_at": str(t.created_at),
            "completed_at": str(t.completed_at) if t.completed_at else None,
        }
        for t in task_result.scalars().all()
    ]

    # Interactions
    int_result = await db.execute(
        select(Interaction).where(
            (Interaction.from_agent_id == agent_id)
            | (Interaction.to_agent_id == agent_id)
        )
    )
    interactions = [
        {
            "id": i.id,
            "task_id": i.task_id,
            "from_agent_id": i.from_agent_id,
            "to_agent_id": i.to_agent_id,
            "outcome": i.outcome,
            "created_at": str(i.created_at),
        }
        for i in int_result.scalars().all()
    ]

    # Intents
    intent_result = await db.execute(
        select(Intent).where(Intent.from_agent_id == agent_id)
    )
    intents = [
        {
            "id": it.id,
            "category": it.category,
            "description": it.description,
            "status": it.status,
            "created_at": str(it.created_at),
        }
        for it in intent_result.scalars().all()
    ]

    # Circle memberships
    cm_result = await db.execute(
        select(CircleMembership).where(CircleMembership.agent_id == agent_id)
    )
    circles = [
        {
            "circle_id": cm.circle_id,
            "role": cm.role,
            "joined_at": str(cm.created_at),
        }
        for cm in cm_result.scalars().all()
    ]

    # Verifications
    ver_result = await db.execute(
        select(Verification).where(Verification.agent_id == agent_id)
    )
    verifications = [
        {
            "method": v.method,
            "status": v.status,
            "created_at": str(v.created_at),
        }
        for v in ver_result.scalars().all()
    ]

    now = datetime.now(timezone.utc)
    return {
        "export_version": "1.0",
        "exported_at": str(now),
        "agent": {
            "id": agent.id,
            "slug": agent.slug,
            "display_name": agent.display_name,
            "agent_type": agent.agent_type,
            "owner_type": agent.owner_type,
            "verification_level": agent.verification_level,
            "visibility_scope": agent.visibility_scope,
            "contact_policy": agent.contact_policy,
            "status": agent.status,
            "region": agent.region,
            "created_at": str(agent.created_at),
            "updated_at": str(agent.updated_at),
        },
        "profile": profile_data,
        "field_visibilities": field_vis,
        "relationships": relationships,
        "tasks": tasks,
        "interactions": interactions,
        "intents": intents,
        "circle_memberships": circles,
        "verifications": verifications,
    }


async def rotate_api_key(db: AsyncSession, agent: Agent) -> str:
    """Rotate agent's API key. Returns new key (shown once only).

    Old key is immediately invalidated.
    """
    new_key = generate_api_key()
    agent.api_key_hash = hash_api_key(new_key)
    agent.api_key_prefix = extract_key_prefix(new_key)
    agent.key_rotated_at = datetime.now(timezone.utc)
    await db.flush()
    return new_key


async def update_last_seen(db: AsyncSession, agent: Agent) -> None:
    """Update agent's last_seen_at timestamp (called on each API request)."""
    agent.last_seen_at = datetime.now(timezone.utc)


async def compute_verification_level(db: AsyncSession, agent_id: str) -> str:
    """Compute highest verification level from all completed verifications (spec §14.4)."""
    result = await db.execute(
        select(Verification).where(
            Verification.agent_id == agent_id,
            Verification.status == "verified",
        )
    )
    verifications = result.scalars().all()

    max_weight = 0
    max_level = "none"
    for v in verifications:
        try:
            level = VerificationLevel(v.method)
            weight = VERIFICATION_WEIGHTS.get(level, 0)
            if weight > max_weight:
                max_weight = weight
                max_level = v.method
        except ValueError:
            continue

    return max_level
