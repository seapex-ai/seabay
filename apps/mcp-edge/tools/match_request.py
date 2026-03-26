"""P0 Tool: match_request — intelligent agent matching with ranked candidates.

Risk level: R0 (pure information)
Auth: authless (no OAuth required)

Wraps the Core API POST /v1/match endpoint. Preferred over raw search_agents
for natural-language flows — produces richer, explainable results with
candidate buckets and recommended actions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from config import settings
from middleware.risk_gate import check_risk

logger = logging.getLogger("mcp-edge.tools.match_request")

router = APIRouter()


# ── MCP Tool Schema ──

TOOL_SCHEMA = {
    "name": "match_request",
    "description": (
        "Find the best agents for a task using intelligent matching. "
        "Provide a natural-language description of what you need, along with "
        "optional structured hints (skills, location, language). Returns ranked "
        "candidates with match reasons and a recommended next action. "
        "Prefer this over search_agents for richer, explainable results."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Natural-language description of what the user needs",
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Desired skills or activity types, e.g. ['translation', 'japanese']",
            },
            "language": {
                "type": "string",
                "description": "Language requirement, e.g. 'ja', 'en', 'zh'",
            },
            "location": {
                "type": "string",
                "description": "City or region preference",
            },
            "task_type": {
                "type": "string",
                "enum": ["collaboration", "delegation", "introduction", "exchange"],
                "description": "Type of task intended",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "maximum": 20,
            },
        },
        "required": ["description"],
    },
}


class MatchRequestInput(BaseModel):
    description: str
    skills: list[str] | None = None
    language: str | None = None
    location: str | None = None
    task_type: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/match_request")
async def match_request(
    req: MatchRequestInput,
    request: Request,
):
    """Execute match_request tool — R0, authless.

    Calls Core API POST /v1/match with natural-language description
    and optional structured hints. Returns MCP-formatted response
    with candidate buckets, reasons, and recommended action.
    """
    check_risk("R0", tool_name="match_request")

    body: dict = {
        "description": req.description,
        "limit": req.limit,
    }
    if req.skills:
        body["skills"] = req.skills
    if req.language:
        body["languages"] = [req.language]
    if req.location:
        body["location"] = req.location
    if req.task_type:
        body["task_type"] = req.task_type

    # Propagate trace_id from upstream or generate one
    trace_id = request.headers.get("x-trace-id") or f"trc_{req.description[:8]}"

    core_client = request.app.state.core_client
    try:
        response = await core_client.post("/match", json=body)
        response.raise_for_status()
        core_data = response.json()
        # Prefer trace_id from Core API response (middleware-generated)
        trace_id = core_data.get("trace_id") or response.headers.get("x-trace-id") or trace_id
    except Exception as e:
        logger.error("Core API match failed: %s", e)
        return _empty_response(req.description, trace_id)

    buckets = core_data.get("candidate_buckets", {})
    top = buckets.get("top_matches", [])
    also = buckets.get("also_relevant", [])
    all_matches = top + also

    if not all_matches:
        return _empty_response(req.description, trace_id)

    best = top[0] if top else all_matches[0]

    return {
        "summary_text": core_data.get("summary_text", f"Found {len(all_matches)} candidate(s)."),
        "trace_id": core_data.get("trace_id"),
        "data": {
            "candidate_buckets": {
                "top_matches": top,
                "also_relevant": also,
            },
            "total_matches": core_data.get("total_matches", len(all_matches)),
        },
        "suggested_action": core_data.get("recommended_action") or {
            "type": "create_task",
            "target_id": best.get("agent_id"),
            "reason": f"Best match: {best.get('display_name', 'unknown')}",
        },
        "next_actions": ["create_task", "get_agent_profile"],
        "fallback_url": core_data.get("fallback_url", f"{settings.FALLBACK_BASE_URL}/search"),
    }


@router.get("/match_request/schema")
async def match_request_schema():
    """Return the MCP tool schema for match_request."""
    return TOOL_SCHEMA


def _empty_response(description: str, trace_id: str | None = None) -> dict:
    return {
        "summary_text": f"No matching agents found for: {description[:100]}",
        "trace_id": trace_id,
        "data": {"candidate_buckets": {"top_matches": [], "also_relevant": []}, "total_matches": 0},
        "suggested_action": None,
        "fallback_message": (
            "The network is still growing. Try broadening your request "
            "or check back later as new agents register."
        ),
        "next_actions": [],
        "fallback_url": f"{settings.FALLBACK_BASE_URL}/search",
    }
