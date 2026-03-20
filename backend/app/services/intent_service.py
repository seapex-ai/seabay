"""Intent service — publishing, matching algorithm, candidate ranking.

Covers spec §11 (intent system), §13 (matching engine).
V1.5 uses deterministic rules-first matching (no embedding/semantic).

Open-Core: Reference implementation with default weights.
Production deployment may override weights via app.hosted.weights.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ContactPolicyDeniedError, InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent, Profile
from app.models.enums import (
    HIGH_RISK_KEYWORDS,
    RiskLevel,
    TaskStatus,
    requires_human_confirm,
)
from app.models.intent import Intent
from app.models.relationship import RelationshipEdge
from app.models.task import Task
from app.services import relationship_service as rel_service
from app.services.task_service import run_dlp_scan

# Hosted weight overrides (graceful fallback to defaults)
try:
    from app.hosted.weights import MATCHING_WEIGHTS as _HOSTED_WEIGHTS
except ImportError:
    _HOSTED_WEIGHTS = None

# Default matching weights (open-core)
_DEFAULT_WEIGHTS = {
    "skills_match": 30,
    "languages_match": 15,
    "location_match": 10,
    "verification_level": 10,
    "service_type_bonus": 5,
    "relationship_bonus": 15,
    "circle_bonus": 10,
    "availability_bonus": 5,
}

WEIGHTS = _HOSTED_WEIGHTS if _HOSTED_WEIGHTS is not None else _DEFAULT_WEIGHTS


async def get_intent(db: AsyncSession, intent_id: str) -> Intent:
    """Get intent by ID or raise NotFoundError."""
    result = await db.execute(select(Intent).where(Intent.id == intent_id))
    intent = result.scalar_one_or_none()
    if not intent:
        raise NotFoundError("Intent")
    return intent


async def create_intent(
    db: AsyncSession,
    agent: Agent,
    category: str,
    description: str,
    structured_requirements: Optional[dict] = None,
    audience_scope: str = "public",
    ttl_hours: int = 72,
    max_matches: int = 5,
) -> Intent:
    """Create a new intent with DLP scanning."""
    intent_id = generate_id("intent")

    # DLP scan on description
    await run_dlp_scan(db, "intent", intent_id, description)

    now = datetime.now(timezone.utc)
    intent = Intent(
        id=intent_id,
        from_agent_id=agent.id,
        category=category,
        description=description,
        structured_requirements=structured_requirements or {},
        audience_scope=audience_scope,
        max_matches=max_matches,
        ttl_hours=ttl_hours,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    db.add(intent)
    await db.flush()
    return intent


async def find_matches(
    db: AsyncSession,
    intent: Intent,
    requester: Agent,
) -> list[dict]:
    """Find matching agent candidates per spec §13.1.

    Matching order (deterministic, NOT ML):
    1. Filter by audience_scope
    2. Filter by visibility rules
    3. Filter by relationship + contact_policy
    4. Structural matching: skill/language/location
    5. Filter by verification + trust
    6. Sort by user preference
    7. Popularity as weak signal only

    Each match must return >= 3 reasons (spec §13.3).
    """
    # Build candidate query — search agents (prefer service agents)
    stmt = (
        select(Agent, Profile)
        .join(Profile, Profile.agent_id == Agent.id)
        .where(
            Agent.status.notin_(["suspended", "banned"]),
            Agent.id != requester.id,
        )
    )

    # Filter by audience_scope
    if intent.audience_scope == "public":
        # Only public agents for public intents
        stmt = stmt.where(Agent.visibility_scope == "public")
    elif intent.audience_scope == "network":
        # Only agents in requester's network
        network_ids = await _get_network_agent_ids(db, requester.id)
        if network_ids:
            stmt = stmt.where(Agent.id.in_(network_ids))
        else:
            return []
    elif intent.audience_scope.startswith("circle:"):
        circle_id = intent.audience_scope.split(":", 1)[1]
        circle_ids = await _get_circle_member_ids(db, circle_id)
        if circle_ids:
            stmt = stmt.where(Agent.id.in_(circle_ids))
        else:
            return []

    result = await db.execute(stmt)
    raw_candidates = result.all()

    # Filter by contact policy (spec §13.1 step 3)
    candidates = []
    for row in raw_candidates:
        agent = row.Agent
        try:
            await rel_service.check_contact_allowed(db, requester, agent)
            candidates.append(row)
        except ContactPolicyDeniedError:
            continue

    # Score and rank
    matches = []
    reqs = intent.structured_requirements or {}
    req_skills = reqs.get("skills", []) or reqs.get("skills_needed", [])
    req_languages = reqs.get("languages", []) or reqs.get("language", [])
    if isinstance(req_languages, str):
        req_languages = [req_languages]
    req_location = reqs.get("location_country") or reqs.get("location")

    for row in candidates:
        agent = row.Agent
        profile = row.Profile
        score = 0.0
        reasons = []

        # Skill match — hard filter when skills are specified
        if req_skills and profile.skills:
            overlap = set(req_skills) & set(profile.skills)
            if overlap:
                score += len(overlap) * WEIGHTS.get("skills_match", 30)
                reasons.append(f"Skills match: {', '.join(sorted(overlap))}")
            else:
                # Hard filter: skip agents with zero skill overlap
                continue
        elif req_skills and not profile.skills:
            # Agent has no skills listed but intent requires specific skills
            continue

        # Description keyword match in skills (20 pts each)
        if profile.skills and not req_skills:
            desc_words = set(intent.description.lower().split())
            skill_match = [s for s in profile.skills if s.lower() in desc_words]
            if skill_match:
                score += len(skill_match) * 20
                reasons.append(f"Skills relevant: {', '.join(skill_match[:3])}")

        # can_offer match
        if req_skills and profile.can_offer:
            offer_overlap = set(req_skills) & set(profile.can_offer)
            if offer_overlap:
                score += len(offer_overlap) * 15
                reasons.append(f"Can offer: {', '.join(sorted(offer_overlap))}")

        # Language match
        if req_languages and profile.languages:
            lang_overlap = set(req_languages) & set(profile.languages)
            if lang_overlap:
                score += len(lang_overlap) * WEIGHTS.get("languages_match", 15)
                reasons.append(f"Languages: {', '.join(sorted(lang_overlap))}")

        # Location match
        if req_location:
            loc_pts = WEIGHTS.get("location_match", 10)
            if profile.location_country == req_location:
                score += loc_pts
                reasons.append(f"Location: {profile.location_country}")
            elif profile.location_city and req_location.lower() == profile.location_city.lower():
                score += loc_pts
                reasons.append(f"Location: {profile.location_city}")

        # Verification bonus
        if agent.verification_level != "none":
            score += WEIGHTS.get("verification_level", 10)
            reasons.append(f"Verified: {agent.verification_level}")

        # Service agent type bonus
        if agent.agent_type == "service":
            score += WEIGHTS.get("service_type_bonus", 5)
            if not any("service" in r.lower() for r in reasons):
                reasons.append("Service agent")

        # Relationship bonus
        edge = await _get_edge_fast(db, requester.id, agent.id)
        if edge and not edge.is_blocked:
            if edge.strength in ("trusted", "frequent"):
                score += WEIGHTS.get("relationship_bonus", 15)
                reasons.append(f"Trusted relationship ({edge.strength})")
            elif edge.strength == "acquaintance":
                score += 8
                reasons.append("Previous collaborator")

        # Ensure minimum 3 reasons
        _pad_reasons(reasons, profile)

        if score > 0:
            matches.append({
                "agent_id": agent.id,
                "display_name": agent.display_name,
                "agent_type": agent.agent_type,
                "verification_level": agent.verification_level,
                "trust_tier": _compute_trust_tier(edge),
                "match_score": round(score, 2),
                "reasons": reasons[:5],
                "badges": _compute_badges(agent),
            })

    # Sort by score descending, limit to max_matches
    matches.sort(key=lambda m: m["match_score"], reverse=True)
    return matches[: intent.max_matches]


async def select_candidate(
    db: AsyncSession,
    intent: Intent,
    agent: Agent,
    selected_agent_id: str,
    description: Optional[str] = None,
    payload_ref: Optional[str] = None,
    payload_inline: Optional[dict] = None,
) -> Task:
    """Select a match candidate and create a Task from the intent."""
    if intent.from_agent_id != agent.id:
        raise InvalidRequestError("Can only select for your own intents")

    if intent.status in ("fulfilled", "expired", "cancelled"):
        raise InvalidRequestError(f"Intent is {intent.status}")

    # Verify target exists and is contactable
    target_result = await db.execute(
        select(Agent).where(Agent.id == selected_agent_id)
    )
    target = target_result.scalar_one_or_none()
    if not target:
        raise NotFoundError("Target agent")
    if target.status in ("suspended", "banned"):
        raise InvalidRequestError(f"Target agent is {target.status}")

    # Enforce contact policy (spec §10.1)
    await rel_service.check_contact_allowed(db, agent, target)

    # Detect risk level
    risk = RiskLevel.R0
    desc_lower = (description or intent.description or "").lower()
    for keyword, level in HIGH_RISK_KEYWORDS.items():
        if keyword in desc_lower:
            if level.value > risk.value:
                risk = level

    # DLP scan
    task_id = generate_id("task")
    scan_text = description or intent.description or ""
    if scan_text:
        await run_dlp_scan(db, "task", task_id, scan_text)

    now = datetime.now(timezone.utc)
    task = Task(
        id=task_id,
        idempotency_key=generate_id("task"),  # auto-generate for intent-based tasks
        from_agent_id=agent.id,
        to_agent_id=selected_agent_id,
        intent_id=intent.id,
        task_type=intent.category,
        description=description or intent.description,
        payload_ref=payload_ref,
        payload_inline=payload_inline,
        risk_level=risk.value,
        status=TaskStatus.PENDING_DELIVERY.value,
        requires_human_confirm=requires_human_confirm(risk),
        expires_at=now + timedelta(hours=72),
    )
    db.add(task)

    intent.status = "fulfilled"
    await db.flush()
    return task


# ── Helpers ──

async def _get_network_agent_ids(db: AsyncSession, agent_id: str) -> list[str]:
    """Get IDs of agents in the requester's network."""
    result = await db.execute(
        select(RelationshipEdge.to_agent_id).where(
            RelationshipEdge.from_agent_id == agent_id,
            RelationshipEdge.is_blocked == False,  # noqa: E712
        )
    )
    return [row[0] for row in result.all()]


async def _get_circle_member_ids(db: AsyncSession, circle_id: str) -> list[str]:
    """Get IDs of agents in a circle."""
    from app.models.circle import CircleMembership
    result = await db.execute(
        select(CircleMembership.agent_id).where(
            CircleMembership.circle_id == circle_id,
        )
    )
    return [row[0] for row in result.all()]


async def _get_edge_fast(
    db: AsyncSession, from_id: str, to_id: str,
) -> Optional[RelationshipEdge]:
    """Quick edge lookup for scoring."""
    result = await db.execute(
        select(RelationshipEdge).where(
            RelationshipEdge.from_agent_id == from_id,
            RelationshipEdge.to_agent_id == to_id,
        )
    )
    return result.scalar_one_or_none()


def _compute_trust_tier(edge: Optional[RelationshipEdge]) -> Optional[str]:
    """Compute trust tier for display."""
    if not edge:
        return None
    return edge.strength if edge.strength != "new" else None


def _compute_badges(agent: Agent) -> list[str]:
    """Compute display badges for an agent."""
    badges = []
    if agent.verification_level != "none":
        badges.append(agent.verification_level)
    if agent.agent_type == "service":
        badges.append("service_agent")
    return badges


def _pad_reasons(reasons: list[str], profile: Profile) -> None:
    """Ensure at least 3 reasons (spec requirement)."""
    while len(reasons) < 3:
        if profile.bio and not any("profile" in r.lower() for r in reasons):
            reasons.append("Active agent with profile")
        elif profile.can_offer and not any("offer" in r.lower() for r in reasons):
            reasons.append(f"Offers: {', '.join(profile.can_offer[:3])}")
        elif profile.languages and not any("language" in r.lower() for r in reasons):
            reasons.append(f"Supports: {', '.join(profile.languages[:3])}")
        else:
            reasons.append("Available for collaboration")
            break
