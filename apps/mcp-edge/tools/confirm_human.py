"""P0 Tool: confirm_human — human approval for high-risk operations.

Risk level: N/A (this IS the approval action)
Auth: OAuth required

Used when create_task returns approval_required (R2/R3).
The user confirms or rejects via this tool, or via the fallback URL.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from config import settings
from auth.oauth import require_scope
from auth.jwt import create_core_auth_header

logger = logging.getLogger("mcp-edge.tools.confirm_human")

router = APIRouter()

TOOL_SCHEMA = {
    "name": "confirm_human",
    "description": (
        "Confirm or reject a high-risk action that requires human approval. "
        "Use this when a previous tool call (like create_task) returned "
        "status 'approval_required'. You must provide the task_id and your "
        "decision (approve, reject, or approve_once)."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["task_id", "decision"],
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID requiring confirmation",
            },
            "decision": {
                "type": "string",
                "enum": ["approve", "reject", "approve_once"],
                "description": "Your decision: approve, reject, or approve_once",
            },
            "token": {
                "type": "string",
                "description": "Approval token (if provided in the approval object)",
            },
        },
    },
}


class ConfirmHumanInput(BaseModel):
    task_id: str
    decision: str  # approve, reject, approve_once
    token: str | None = None


@router.post("/confirm_human")
async def confirm_human(
    req: ConfirmHumanInput,
    request: Request,
    auth: dict = Depends(require_scope("task.confirm")),
):
    """Execute confirm_human tool — OAuth required.

    Calls Core API POST /v1/tasks/{id}/confirm-human with the user's decision.
    """
    if req.decision not in ("approve", "reject", "approve_once"):
        return {
            "summary_text": "Invalid decision. Must be 'approve', 'reject', or 'approve_once'.",
            "data": {"error": "invalid_decision"},
            "next_actions": ["confirm_human"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/tasks/{req.task_id}",
        }

    confirmed = req.decision in ("approve", "approve_once")

    headers = create_core_auth_header(
        subject=auth["subject"],
        scopes=auth["scopes"],
        agent_id=auth.get("agent_id"),
    )

    confirm_body = {
        "confirmed": confirmed,
    }
    if req.token:
        confirm_body["token"] = req.token

    core_client = request.app.state.core_client
    try:
        response = await core_client.post(
            f"/tasks/{req.task_id}/confirm-human",
            json=confirm_body,
            headers=headers,
        )
        response.raise_for_status()
        task_data = response.json()
    except Exception as e:
        logger.error("Core API confirm_human failed for %s: %s", req.task_id, e)
        return {
            "summary_text": f"Failed to process your confirmation for task {req.task_id}.",
            "data": {"error": str(e)},
            "next_actions": ["confirm_human", "get_task"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/tasks/{req.task_id}",
        }

    if confirmed:
        new_status = task_data.get("status", "unknown")
        return {
            "summary_text": (
                f"Task {req.task_id} has been approved. "
                f"Current status: {new_status}."
            ),
            "data": {
                "task_id": req.task_id,
                "decision": req.decision,
                "new_status": new_status,
            },
            "next_actions": ["get_task"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/tasks/{req.task_id}",
        }
    else:
        return {
            "summary_text": f"Task {req.task_id} has been rejected.",
            "data": {
                "task_id": req.task_id,
                "decision": "reject",
                "new_status": "cancelled",
            },
            "next_actions": ["search_agents"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/tasks",
        }


@router.get("/confirm_human/schema")
async def confirm_human_schema():
    """Return the MCP tool schema for confirm_human."""
    return TOOL_SCHEMA
