"""Match service — orchestrates intent creation + matching + bucket formation.

Part of the Remote MCP Server v1.0 spec (P1 tool: match_request).
Uses intent_service.create_intent + intent_service.find_matches internally,
then applies bucket splitting and summary generation.
"""

from __future__ import annotations

from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.services import intent_service

# Score threshold for splitting into top_matches vs also_relevant.
# Agents scoring >= this threshold go into top_matches.
TOP_MATCH_SCORE_THRESHOLD = 25.0

# Fallback base URL for constructing web search links
FALLBACK_BASE_URL = "https://app.seabay.ai/search"


async def match_request(
    db: AsyncSession,
    agent: Agent,
    description: str,
    skills: list[str] | None = None,
    languages: list[str] | None = None,
    location: str | None = None,
    audience_scope: str = "public",
    time_window: str | None = None,
) -> dict:
    """Orchestrate match: create intent -> find matches -> build response.

    Returns a dict conforming to MatchResponse schema:
      - recommended_action
      - candidate_buckets (top_matches, also_relevant)
      - summary_text
      - fallback_url
      - intent_id
      - total_matches
    """
    # Build structured requirements from match params
    structured_requirements: dict = {}
    if skills:
        structured_requirements["skills"] = skills
    if languages:
        structured_requirements["languages"] = languages
    if location:
        structured_requirements["location"] = location
        structured_requirements["location_country"] = location
    if time_window:
        structured_requirements["time_window"] = time_window

    # Step 1: Create intent
    intent = await intent_service.create_intent(
        db,
        agent=agent,
        category="service_request",
        description=description,
        structured_requirements=structured_requirements,
        audience_scope=audience_scope,
        ttl_hours=24,
        max_matches=20,
    )

    # Step 2: Find matches
    matches = await intent_service.find_matches(db, intent, agent)

    if matches:
        intent.status = "matched"
        await db.flush()

    # Step 3: Build candidate buckets
    buckets = build_candidate_buckets(matches)

    # Step 4: Build summary text
    summary = build_summary_text(matches, skills=skills, location=location)

    # Step 5: Build fallback URL
    fallback_url = _build_fallback_url(skills=skills, location=location)

    # Step 6: Build recommended action
    recommended_action = None
    top = buckets["top_matches"]
    if top:
        best = top[0]
        recommended_action = {
            "type": "create_task",
            "target_id": best["agent_id"],
            "reason": _build_recommendation_reason(best),
        }

    return {
        "recommended_action": recommended_action,
        "candidate_buckets": buckets,
        "summary_text": summary,
        "fallback_url": fallback_url,
        "intent_id": intent.id,
        "trace_id": generate_id("trc"),
        "total_matches": len(matches),
    }


def build_candidate_buckets(matches: list[dict]) -> dict:
    """Split matches into score-based and type-based pools.

    Score-based: top_matches (>= threshold) vs also_relevant.
    Type-based: service_matches, people_matches, publication_matches, intro_matches.
    """
    top_matches = []
    also_relevant = []
    service_matches = []
    people_matches = []
    publication_matches = []
    intro_matches = []

    for m in matches:
        candidate = _match_to_candidate(m)

        # Score-based bucketing
        if m.get("match_score", 0) >= TOP_MATCH_SCORE_THRESHOLD:
            top_matches.append(candidate)
        else:
            also_relevant.append(candidate)

        # Type-based bucketing by agent_type or match source
        agent_type = m.get("agent_type", "service")
        match_source = m.get("match_source", "")
        if match_source == "publication" or agent_type == "publication":
            publication_matches.append(candidate)
        elif match_source == "introduction" or agent_type == "intro":
            intro_matches.append(candidate)
        elif agent_type == "personal":
            people_matches.append(candidate)
        else:
            service_matches.append(candidate)

    return {
        "top_matches": top_matches,
        "also_relevant": also_relevant,
        "service_matches": service_matches,
        "people_matches": people_matches,
        "publication_matches": publication_matches,
        "intro_matches": intro_matches,
    }


def build_summary_text(
    matches: list[dict],
    skills: list[str] | None = None,
    location: str | None = None,
) -> str:
    """Generate human-readable summary text for the match results.

    This text is consumed by the LLM host (Claude/ChatGPT) to produce
    the user-facing response.
    """
    total = len(matches)
    top_count = sum(
        1 for m in matches
        if m.get("match_score", 0) >= TOP_MATCH_SCORE_THRESHOLD
    )

    # Build context description
    context_parts = []
    if skills:
        context_parts.append(", ".join(skills))
    if location:
        context_parts.append(f"in {location}")
    context = " ".join(context_parts) if context_parts else "your request"

    if total == 0:
        return (
            f"No agents found matching {context} yet. "
            "The network is still growing. Try broadening your search "
            "or check back later as new agents register."
        )

    if top_count == 1:
        best = matches[0]
        name = best.get("display_name", "an agent")
        return (
            f"Found {total} agent(s) for {context}. "
            f"{name} is the best match."
        )

    if top_count > 1:
        return (
            f"Found {total} agent(s) for {context}, "
            f"with {top_count} strong matches."
        )

    return (
        f"Found {total} potentially relevant agent(s) for {context}, "
        "but none are a strong match. You may want to refine your criteria."
    )


def _match_to_candidate(m: dict) -> dict:
    """Transform an intent_service match dict to MCP candidate format."""
    trust = m.get("trust_summary", {})
    if not trust:
        trust = {
            "trust_tier": m.get("trust_tier"),
            "verification_level": m.get("verification_level", "none"),
            "badges": m.get("badges", []),
        }
    agent_id = m.get("agent_id", "")
    return {
        "agent_id": agent_id,
        "display_name": m.get("display_name", ""),
        "description": None,
        "location": None,
        "skills": [],
        "verification_level": m.get("verification_level", "none"),
        "last_active": None,
        "trust_summary": trust,
        "why_matched": m.get("reasons", []),
        "match_score": m.get("match_score", 0.0),
        "profile_url": f"https://seabay.ai/agents/{agent_id}" if agent_id else None,
    }


def _build_fallback_url(
    skills: list[str] | None = None,
    location: str | None = None,
) -> str:
    """Build web fallback URL for non-MCP clients."""
    params = {}
    if skills:
        params["skills"] = ",".join(skills)
    if location:
        params["location"] = location
    if params:
        return f"{FALLBACK_BASE_URL}?{urlencode(params)}"
    return FALLBACK_BASE_URL


def _build_recommendation_reason(candidate: dict) -> str:
    """Build a concise reason string for the recommended action."""
    parts = []
    reasons = candidate.get("why_matched", [])
    if reasons:
        parts.append(reasons[0])
    vl = candidate.get("verification_level", "none")
    if vl != "none":
        parts.append(f"verified ({vl})")
    if not parts:
        parts.append("Best available match")
    return "; ".join(parts)
