"""P0 Tool: search_agents — search for agents by skills, location, language.

Risk level: R0 (pure information)
Auth: authless (no OAuth required)

This is the most critical V1.0 tool. The tool description quality directly
determines whether the LLM can correctly invoke it.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from config import settings
from middleware.risk_gate import check_risk

logger = logging.getLogger("mcp-edge.tools.search_agents")

router = APIRouter()


# ── MCP Tool Schema ──

TOOL_SCHEMA = {
    "name": "search_agents",
    "description": (
        "Search for agents that can help with a specific task or activity. "
        "Always extract structured fields (skills, location, language) from the "
        "user's request rather than passing raw natural language as the query. "
        "For activity requests (sports, meetups, events), search for organizer "
        "or host agents in the relevant location. The query field is only for "
        "cases where structured fields cannot fully capture the intent."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free text search, used only when structured fields cannot capture the intent",
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific skills or activity types, e.g. ['football', 'match_hosting', 'translation']",
            },
            "language": {
                "type": "string",
                "description": "Language requirement, e.g. 'ja', 'en', 'zh'",
            },
            "location": {
                "type": "string",
                "description": "City or region. When provided, only agents in this location will be returned",
            },
            "verification_min": {
                "type": "string",
                "enum": ["none", "email", "github", "domain"],
                "description": "Minimum verification level required",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "maximum": 20,
            },
        },
    },
}


class SearchAgentsInput(BaseModel):
    query: str | None = None
    skills: list[str] | None = None
    language: str | None = None
    location: str | None = None
    verification_min: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/search_agents")
async def search_agents(
    req: SearchAgentsInput,
    request: Request,
):
    """Execute search_agents tool — R0, authless.

    Calls Core API GET /v1/agents/search with structured parameters.
    Returns MCP-formatted response with summary_text, data, next_actions, fallback_url.
    """
    # Risk check — R0 always passes
    check_risk("R0", tool_name="search_agents")

    # Build Core API query params
    params: dict = {"limit": req.limit}
    if req.query:
        params["q"] = req.query
    if req.skills:
        params["skills"] = ",".join(req.skills)
    if req.language:
        params["languages"] = req.language
    if req.location:
        params["location_city"] = req.location
    if req.verification_min:
        params["verification_level"] = req.verification_min

    # Call Core API
    core_client = request.app.state.core_client
    try:
        response = await core_client.get("/agents/search", params=params)
        response.raise_for_status()
        core_data = response.json()
    except Exception as e:
        logger.error("Core API search failed: %s", e)
        return _empty_response(req.skills, req.location)

    matches = core_data.get("data", [])

    if not matches:
        return _empty_response(req.skills, req.location)

    # Transform to MCP format
    formatted_matches = []
    for agent in matches:
        formatted_matches.append({
            "agent_id": agent.get("id", ""),
            "display_name": agent.get("display_name", ""),
            "description": agent.get("bio"),
            "location": agent.get("location_country"),
            "skills": agent.get("skills", []),
            "verification_level": agent.get("verification_level", "none"),
            "last_active": None,
            "trust_summary": {},
            "why_matched": _build_why_matched(agent, req),
        })

    # Build context for summary
    context = _build_context(req)
    best = formatted_matches[0] if formatted_matches else None

    return {
        "summary_text": f"Found {len(formatted_matches)} agent(s) matching {context}.",
        "data": {
            "matches": formatted_matches,
        },
        "suggested_action": {
            "type": "create_task",
            "target_id": best["agent_id"],
            "reason": f"Best match: {best['display_name']}",
        } if best else None,
        "fallback_message": None,
        "next_actions": ["create_task", "get_agent_profile"] if formatted_matches else [],
        "fallback_url": _build_fallback_url(req),
    }


@router.get("/search_agents/schema")
async def search_agents_schema():
    """Return the MCP tool schema for search_agents."""
    return TOOL_SCHEMA


def _empty_response(skills: list[str] | None, location: str | None) -> dict:
    """Build response for zero search results."""
    context = _build_context_from_parts(skills, location)
    return {
        "summary_text": f"No agents found matching {context} yet.",
        "data": {"matches": []},
        "suggested_action": None,
        "fallback_message": (
            "The network is still growing. You could try broadening your search "
            "to nearby areas, or check back later as new agents register."
        ),
        "next_actions": [],
        "fallback_url": _build_fallback_url_from_parts(skills, location),
    }


def _build_why_matched(agent: dict, req: SearchAgentsInput) -> list[str]:
    """Build human-readable why_matched reasons."""
    reasons = []
    if req.location and agent.get("location_country"):
        reasons.append(f"Location: {agent['location_country']}")
    agent_skills = set(agent.get("skills", []))
    if req.skills:
        overlap = agent_skills & set(req.skills)
        if overlap:
            reasons.append(f"Skill match: {', '.join(sorted(overlap))}")
    if agent.get("verification_level", "none") != "none":
        reasons.append(f"Verified: {agent['verification_level']}")
    if not reasons:
        reasons.append("Available for collaboration")
    return reasons


def _build_context(req: SearchAgentsInput) -> str:
    """Build context string from search input."""
    return _build_context_from_parts(req.skills, req.location)


def _build_context_from_parts(skills: list[str] | None, location: str | None) -> str:
    parts = []
    if skills:
        parts.append(", ".join(skills))
    if location:
        parts.append(f"in {location}")
    return " ".join(parts) if parts else "your request"


def _build_fallback_url(req: SearchAgentsInput) -> str:
    return _build_fallback_url_from_parts(req.skills, req.location)


def _build_fallback_url_from_parts(skills: list[str] | None, location: str | None) -> str:
    base = f"{settings.FALLBACK_BASE_URL}/search"
    params = []
    if skills:
        params.append(f"skills={','.join(skills)}")
    if location:
        params.append(f"location={location}")
    if params:
        return f"{base}?{'&'.join(params)}"
    return base
