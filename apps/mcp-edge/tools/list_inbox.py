"""P0 Tool: list_inbox — view incoming tasks (tasks sent to the user's agent).

Risk level: R0 (pure information)
Auth: OAuth required
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from config import settings
from auth.oauth import require_scope
from auth.jwt import create_core_auth_header
from middleware.risk_gate import check_risk

logger = logging.getLogger("mcp-edge.tools.list_inbox")

router = APIRouter()

TOOL_SCHEMA = {
    "name": "list_inbox",
    "description": (
        "View your inbox — tasks that other agents have sent to you. "
        "Shows pending, delivered, and waiting tasks by default. "
        "You can filter by status to see completed or declined tasks."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Filter by task status (e.g. 'pending_accept', 'completed')",
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "maximum": 50,
                "description": "Maximum number of tasks to return",
            },
        },
    },
}


class ListInboxInput(BaseModel):
    status: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


@router.post("/list_inbox")
async def list_inbox(
    req: ListInboxInput,
    request: Request,
    auth: dict = Depends(require_scope("task.inbox.read")),
):
    """Execute list_inbox tool — R0, OAuth required.

    Calls Core API GET /v1/tasks/inbox and returns inbox items in MCP format.
    """
    check_risk("R0", tool_name="list_inbox")

    headers = create_core_auth_header(
        subject=auth["subject"],
        scopes=auth["scopes"],
        agent_id=auth.get("agent_id"),
    )

    params: dict = {"limit": req.limit}
    if req.status:
        params["status"] = req.status

    core_client = request.app.state.core_client
    try:
        response = await core_client.get("/tasks/inbox", params=params, headers=headers)
        response.raise_for_status()
        inbox_data = response.json()
    except Exception as e:
        logger.error("Core API list_inbox failed: %s", e)
        return {
            "summary_text": "Could not retrieve your inbox. Please try again.",
            "data": {"tasks": []},
            "next_actions": ["list_inbox"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/inbox",
        }

    tasks = inbox_data.get("data", [])

    # Transform tasks to MCP-friendly format
    inbox_items = []
    for task in tasks:
        inbox_items.append({
            "task_id": task.get("id"),
            "from_agent_id": task.get("from_agent_id"),
            "task_type": task.get("task_type"),
            "description": task.get("description"),
            "status": task.get("status"),
            "risk_level": task.get("risk_level"),
            "created_at": task.get("created_at"),
        })

    total = len(inbox_items)
    has_more = inbox_data.get("has_more", False)

    if total == 0:
        return {
            "summary_text": "Your inbox is empty. No pending tasks.",
            "data": {"tasks": [], "total": 0, "has_more": False},
            "next_actions": ["search_agents"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/inbox",
        }

    # Build summary
    pending = sum(1 for t in inbox_items if t["status"] in ("pending_accept", "delivered"))
    summary_parts = [f"You have {total} task(s) in your inbox"]
    if pending > 0:
        summary_parts.append(f"{pending} pending your attention")

    return {
        "summary_text": ". ".join(summary_parts) + ".",
        "data": {
            "tasks": inbox_items,
            "total": total,
            "has_more": has_more,
        },
        "next_actions": ["get_task"],
        "fallback_url": f"{settings.FALLBACK_BASE_URL}/inbox",
    }


@router.get("/list_inbox/schema")
async def list_inbox_schema():
    """Return the MCP tool schema for list_inbox."""
    return TOOL_SCHEMA
