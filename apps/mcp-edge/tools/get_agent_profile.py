"""P0 Tool: get_agent_profile — view a single agent's public profile.

Risk level: R0 (pure information)
Auth: authless (no OAuth required)

Returns only whitelisted public-safe fields. Never exposes internal IDs,
raw scores, or debug information.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from config import settings
from middleware.risk_gate import check_risk

logger = logging.getLogger("mcp-edge.tools.get_agent_profile")

router = APIRouter()

TOOL_SCHEMA = {
    "name": "get_agent_profile",
    "description": (
        "Get the public profile of a specific agent by ID. "
        "Returns the agent's display name, bio, skills, languages, "
        "location, verification level, and availability status."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["agent_id"],
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "Agent ID (agt_xxx format)",
            },
        },
    },
}


class GetAgentProfileInput(BaseModel):
    agent_id: str


@router.post("/get_agent_profile")
async def get_agent_profile(req: GetAgentProfileInput, request: Request):
    """Execute get_agent_profile tool — R0, authless.

    Calls Core API GET /v1/agents/{id} and returns whitelisted fields
    in MCP format.
    """
    check_risk("R0", tool_name="get_agent_profile")

    core_client = request.app.state.core_client
    try:
        response = await core_client.get(f"/agents/{req.agent_id}")
        response.raise_for_status()
        agent = response.json()
    except Exception as e:
        logger.error("Core API get_agent failed for %s: %s", req.agent_id, e)
        return {
            "summary_text": f"Agent {req.agent_id} not found or unavailable.",
            "data": None,
            "next_actions": ["search_agents"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/agents",
        }

    # Extract profile fields (whitelist approach)
    profile = agent.get("profile", {}) or {}
    agent_data = {
        "agent_id": agent.get("id"),
        "display_name": agent.get("display_name"),
        "agent_type": agent.get("agent_type"),
        "bio": profile.get("bio"),
        "skills": profile.get("skills", []),
        "languages": profile.get("languages", []),
        "location_city": profile.get("location_city"),
        "location_country": profile.get("location_country"),
        "verification_level": agent.get("verification_level", "none"),
        "status": agent.get("status"),
        "can_offer": profile.get("can_offer", []),
        "pricing_hint": profile.get("pricing_hint"),
    }

    name = agent_data["display_name"] or req.agent_id
    skills_text = ", ".join(agent_data["skills"][:5]) if agent_data["skills"] else "not specified"

    return {
        "summary_text": (
            f"{name} — {agent_data['agent_type'] or 'agent'}. "
            f"Skills: {skills_text}. "
            f"Verification: {agent_data['verification_level']}."
        ),
        "data": agent_data,
        "next_actions": ["create_task", "search_agents"],
        "fallback_url": f"{settings.FALLBACK_BASE_URL}/agents/{req.agent_id}",
    }


@router.get("/get_agent_profile/schema")
async def get_agent_profile_schema():
    """Return the MCP tool schema for get_agent_profile."""
    return TOOL_SCHEMA
