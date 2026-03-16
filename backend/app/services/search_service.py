"""Search service — agent discovery and directory listing.

Open-Core: Reference implementation with default ranking weights.
Production deployment may override weights via app.hosted.weights.

Handles search logic extracted from route handlers:
- Full-text search across agent display names, skills, bio
- Public directory listing with sorting and pagination
- Activity summary computation
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, Profile, ProfileFieldVisibility
from app.models.circle import CircleMembership
from app.models.relationship import RelationshipEdge
from app.models.task import Task
from app.services.visibility_service import ACCESS_LEVELS, PERSONAL_DEFAULTS, VIEWER_LEVELS

# SQL CASE expression for trust_first sorting using actual verification weights
# manual_review(4) > workspace(3) > github/domain(2) > email(1) > none(0)
_VERIFICATION_WEIGHT_EXPR = case(
    (Agent.verification_level == "manual_review", 4),
    (Agent.verification_level == "workspace", 3),
    (Agent.verification_level == "github", 2),
    (Agent.verification_level == "domain", 2),
    (Agent.verification_level == "email", 1),
    else_=0,
)


async def search_agents(
    db: AsyncSession,
    query: str,
    caller_agent_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    skills: Optional[list[str]] = None,
    languages: Optional[list[str]] = None,
    location_country: Optional[str] = None,
    location_city: Optional[str] = None,
    verification_level: Optional[str] = None,
    sort: str = "relevance",
    cursor: Optional[str] = None,
    limit: int = 20,
) -> tuple[list[dict], Optional[str], bool]:
    """Search agents by query and filters.

    Only returns public agents + network_only agents the caller has
    a relationship with. Results use public-safe fields only.
    """
    # Get agents that consider the caller part of their network
    # (target→caller edge, matching visibility_service._determine_access_level direction)
    network_ids: list[str] = []
    # Get caller's circle co-members for circle_only visibility
    circle_member_ids: list[str] = []
    if caller_agent_id:
        net_result = await db.execute(
            select(RelationshipEdge.from_agent_id).where(
                RelationshipEdge.to_agent_id == caller_agent_id,
                RelationshipEdge.is_blocked.is_(False),
            )
        )
        network_ids = [row[0] for row in net_result.all()]

        # Find agents sharing a circle with the caller
        caller_circles = select(CircleMembership.circle_id).where(
            CircleMembership.agent_id == caller_agent_id,
        ).scalar_subquery()
        circle_result = await db.execute(
            select(CircleMembership.agent_id).where(
                CircleMembership.circle_id.in_(caller_circles),
                CircleMembership.agent_id != caller_agent_id,
            ).distinct()
        )
        circle_member_ids = [row[0] for row in circle_result.all()]

    stmt = (
        select(Agent, Profile)
        .outerjoin(Profile, Profile.agent_id == Agent.id)
        .where(
            Agent.status.notin_(["suspended", "banned"]),
        )
    )

    # Visibility filtering:
    # - public: visible to everyone
    # - network_only: visible only to caller's network connections
    # - circle_only: visible only to co-members of shared circles
    # - private: never appears in search
    vis_conditions = [Agent.visibility_scope == "public"]
    if network_ids:
        vis_conditions.append(
            (Agent.visibility_scope == "network_only") & Agent.id.in_(network_ids)
        )
    if circle_member_ids:
        vis_conditions.append(
            (Agent.visibility_scope == "circle_only") & Agent.id.in_(circle_member_ids)
        )
        # circle co-members can also see network_only agents
        if not network_ids:
            pass  # network_ids already handles this
    stmt = stmt.where(or_(*vis_conditions))

    # Full-text search across display_name, bio, skills
    if query:
        query_pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Agent.display_name.ilike(query_pattern),
                Agent.slug.ilike(query_pattern),
                Profile.bio.ilike(query_pattern),
                func.array_to_string(Profile.skills, " ").ilike(query_pattern),
            )
        )

    # Filters
    if agent_type:
        stmt = stmt.where(Agent.agent_type == agent_type)
    if verification_level:
        stmt = stmt.where(Agent.verification_level == verification_level)
    if location_country:
        stmt = stmt.where(Profile.location_country == location_country)
    if location_city:
        stmt = stmt.where(Profile.location_city == location_city)
    if skills:
        stmt = stmt.where(Profile.skills.overlap(skills))
    if languages:
        stmt = stmt.where(Profile.languages.overlap(languages))

    # Sorting
    if sort == "newest":
        stmt = stmt.order_by(Agent.created_at.desc())
    elif sort == "trust_first":
        stmt = stmt.order_by(_VERIFICATION_WEIGHT_EXPR.desc(), Agent.updated_at.desc())
    else:
        # Default: recent_active / relevance
        stmt = stmt.order_by(Agent.updated_at.desc())

    if cursor:
        stmt = stmt.where(Agent.id > cursor)

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    # Batch-load field visibility overrides for personal agents
    personal_ids = [row.Agent.id for row in rows if row.Agent.agent_type == "personal"]
    field_vis_map = await _batch_load_field_visibility(db, personal_ids)
    network_id_set = set(network_ids)
    circle_id_set = set(circle_member_ids)

    results = []
    for row in rows:
        agent = row.Agent
        profile = row.Profile
        result_dict = _agent_to_search_result(agent, profile)

        # Apply field-level visibility for personal agents
        if agent.agent_type == "personal":
            # Determine viewer level: circle > network > public
            if agent.id in circle_id_set:
                viewer_level = "circle"
            elif agent.id in network_id_set:
                viewer_level = "network"
            else:
                viewer_level = "public"
            result_dict = _filter_search_fields(result_dict, field_vis_map.get(agent.id, {}), viewer_level)

        results.append(result_dict)

    next_cursor = rows[-1].Agent.id if has_more else None
    return results, next_cursor, has_more


async def list_public_agents(
    db: AsyncSession,
    sort: str = "recent_active",
    cursor: Optional[str] = None,
    limit: int = 20,
    skills: Optional[list[str]] = None,
    languages: Optional[list[str]] = None,
    location_country: Optional[str] = None,
) -> tuple[list[dict], Optional[str], bool]:
    """List agents in the public directory.

    Only shows agents with visibility_scope = public.
    Supports optional skill/language/location filters.
    """
    stmt = (
        select(Agent, Profile)
        .outerjoin(Profile, Profile.agent_id == Agent.id)
        .where(
            Agent.status.notin_(["suspended", "banned"]),
            Agent.visibility_scope == "public",
        )
    )

    if skills:
        stmt = stmt.where(Profile.skills.overlap(skills))
    if languages:
        stmt = stmt.where(Profile.languages.overlap(languages))
    if location_country:
        stmt = stmt.where(Profile.location_country == location_country)

    if sort == "newest":
        stmt = stmt.order_by(Agent.created_at.desc())
    elif sort == "trust_first":
        stmt = stmt.order_by(_VERIFICATION_WEIGHT_EXPR.desc(), Agent.updated_at.desc())
    else:
        stmt = stmt.order_by(Agent.updated_at.desc())

    if cursor:
        stmt = stmt.where(Agent.id > cursor)

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    personal_ids = [row.Agent.id for row in rows if row.Agent.agent_type == "personal"]
    field_vis_map = await _batch_load_field_visibility(db, personal_ids)

    results = []
    for row in rows:
        result_dict = _agent_to_search_result(row.Agent, row.Profile)
        if row.Agent.agent_type == "personal":
            result_dict = _filter_search_fields(result_dict, field_vis_map.get(row.Agent.id, {}), "public")
        results.append(result_dict)

    next_cursor = rows[-1].Agent.id if has_more else None
    return results, next_cursor, has_more


async def get_public_agent_card(
    db: AsyncSession,
    slug: str,
) -> Optional[dict]:
    """Get a public agent card by slug."""
    result = await db.execute(
        select(Agent, Profile)
        .outerjoin(Profile, Profile.agent_id == Agent.id)
        .where(Agent.slug == slug, Agent.visibility_scope == "public")
    )
    row = result.first()
    if not row:
        return None
    result_dict = _agent_to_search_result(row.Agent, row.Profile)
    if row.Agent.agent_type == "personal":
        fv_map = await _batch_load_field_visibility(db, [row.Agent.id])
        result_dict = _filter_search_fields(result_dict, fv_map.get(row.Agent.id, {}), "public")
    return result_dict


async def get_activity_summary(
    db: AsyncSession,
    agent_id: str,
) -> dict:
    """Get activity summary for a public agent."""
    # Count completed tasks
    completed = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.status == "completed",
        )
    )
    completed_count = completed.scalar() or 0

    # Count total tasks received
    total = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
        )
    )
    total_count = total.scalar() or 0

    return {
        "tasks_completed": completed_count,
        "tasks_received": total_count,
        "success_rate": round(completed_count / max(total_count, 1), 4),
    }


async def search_public_agents(
    db: AsyncSession,
    query: str,
    skills: Optional[list[str]] = None,
    languages: Optional[list[str]] = None,
    location_country: Optional[str] = None,
    sort: str = "recent_active",
    cursor: Optional[str] = None,
    limit: int = 20,
) -> tuple[list[dict], Optional[str], bool]:
    """Search within public agents only (no auth required).

    Combines full-text search with skill/language/location filtering.
    """
    stmt = (
        select(Agent, Profile)
        .outerjoin(Profile, Profile.agent_id == Agent.id)
        .where(
            Agent.status.notin_(["suspended", "banned"]),
            Agent.visibility_scope == "public",
        )
    )

    # Full-text search across display_name, slug, bio, skills
    if query:
        query_pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Agent.display_name.ilike(query_pattern),
                Agent.slug.ilike(query_pattern),
                Profile.bio.ilike(query_pattern),
                func.array_to_string(Profile.skills, " ").ilike(query_pattern),
            )
        )

    # Skill filter
    if skills:
        stmt = stmt.where(Profile.skills.overlap(skills))

    # Language filter
    if languages:
        stmt = stmt.where(Profile.languages.overlap(languages))

    # Location filter
    if location_country:
        stmt = stmt.where(Profile.location_country == location_country)

    # Sorting
    if sort == "newest":
        stmt = stmt.order_by(Agent.created_at.desc())
    elif sort == "trust_first":
        stmt = stmt.order_by(_VERIFICATION_WEIGHT_EXPR.desc(), Agent.updated_at.desc())
    else:
        stmt = stmt.order_by(Agent.updated_at.desc())

    if cursor:
        stmt = stmt.where(Agent.id > cursor)

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    personal_ids = [row.Agent.id for row in rows if row.Agent.agent_type == "personal"]
    field_vis_map = await _batch_load_field_visibility(db, personal_ids)

    results = []
    for row in rows:
        result_dict = _agent_to_search_result(row.Agent, row.Profile)
        if row.Agent.agent_type == "personal":
            result_dict = _filter_search_fields(result_dict, field_vis_map.get(row.Agent.id, {}), "public")
        results.append(result_dict)

    next_cursor = rows[-1].Agent.id if has_more else None
    return results, next_cursor, has_more


def _agent_to_search_result(agent: Agent, profile: Optional[Profile]) -> dict:
    """Convert agent + profile to public-safe search result dict.

    Only returns fields safe for public/search display.
    Does NOT include location_city, timezone, looking_for, pricing_hint
    (those require field-level visibility checks via visibility_service).
    """
    badges = []
    if agent.verification_level != "none":
        badges.append(agent.verification_level)

    return {
        "id": agent.id,
        "slug": agent.slug,
        "display_name": agent.display_name,
        "agent_type": agent.agent_type,
        "verification_level": agent.verification_level,
        "status": agent.status,
        "bio": profile.bio if profile else None,
        "skills": profile.skills if profile else [],
        "languages": profile.languages if profile else [],
        "location_country": profile.location_country if profile else None,
        "can_offer": profile.can_offer if profile else [],
        "badges": badges,
    }


async def _batch_load_field_visibility(
    db: AsyncSession,
    agent_ids: list[str],
) -> dict[str, dict[str, str]]:
    """Batch-load field visibility overrides for multiple agents."""
    if not agent_ids:
        return {}
    result = await db.execute(
        select(ProfileFieldVisibility).where(
            ProfileFieldVisibility.agent_id.in_(agent_ids),
        )
    )
    vis_map: dict[str, dict[str, str]] = {}
    for v in result.scalars().all():
        vis_map.setdefault(v.agent_id, {})[v.field_name] = v.visibility
    return vis_map


# Profile fields in search results that need visibility filtering
_SEARCH_PROFILE_FIELDS = {"bio", "skills", "languages", "location_country", "can_offer"}


def _filter_search_fields(
    result: dict,
    field_vis: dict[str, str],
    viewer_level: str,
) -> dict:
    """Filter search result profile fields for personal agents.

    Uses PERSONAL_DEFAULTS as baseline, with explicit overrides from field_vis.
    """
    filtered = dict(result)
    viewer_rank = VIEWER_LEVELS.get(viewer_level, 0)

    for field_name in _SEARCH_PROFILE_FIELDS:
        vis = field_vis.get(field_name, PERSONAL_DEFAULTS.get(field_name, "private"))
        if viewer_rank < ACCESS_LEVELS.get(vis, 3):
            # Viewer cannot see this field — redact
            if field_name in ("skills", "languages", "can_offer"):
                filtered[field_name] = []
            else:
                filtered[field_name] = None

    return filtered
