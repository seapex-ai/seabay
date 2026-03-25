"""P0 Tool: get_task — query task status and retrieve results.

Risk level: R0 (pure information)
Auth: OAuth required
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from config import settings
from auth.oauth import require_scope
from auth.jwt import create_core_auth_header
from middleware.risk_gate import check_risk

logger = logging.getLogger("mcp-edge.tools.get_task")

router = APIRouter()

TOOL_SCHEMA = {
    "name": "get_task",
    "description": (
        "Get the current status and result of a task by its ID. "
        "Use this to check if a task has been accepted, completed, "
        "or if there are any results available."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["task_id"],
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID (tsk_xxx format)",
            },
        },
    },
}


class GetTaskInput(BaseModel):
    task_id: str


# Human-readable status descriptions
_STATUS_TEXT = {
    "pending_delivery": "Task is being delivered to the target agent.",
    "delivered": "Task has been delivered and is waiting for the agent to respond.",
    "pending_accept": "Task is waiting for the agent to accept.",
    "accepted": "Task has been accepted by the agent.",
    "in_progress": "Task is currently being worked on.",
    "waiting_human_confirm": "Task requires human confirmation before proceeding.",
    "completed": "Task has been completed successfully.",
    "declined": "Task was declined by the target agent.",
    "expired": "Task has expired.",
    "cancelled": "Task was cancelled.",
    "failed": "Task delivery failed after multiple attempts.",
}


@router.post("/get_task")
async def get_task(
    req: GetTaskInput,
    request: Request,
    auth: dict = Depends(require_scope("task.read")),
):
    """Execute get_task tool — R0, OAuth required.

    Calls Core API GET /v1/tasks/{id} and returns task status in MCP format.
    """
    check_risk("R0", tool_name="get_task")

    headers = create_core_auth_header(
        subject=auth["subject"],
        scopes=auth["scopes"],
        agent_id=auth.get("agent_id"),
    )

    core_client = request.app.state.core_client
    try:
        response = await core_client.get(f"/tasks/{req.task_id}", headers=headers)
        response.raise_for_status()
        task = response.json()
    except Exception as e:
        logger.error("Core API get_task failed for %s: %s", req.task_id, e)
        return {
            "summary_text": f"Could not retrieve task {req.task_id}.",
            "data": None,
            "next_actions": ["list_inbox"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/tasks",
        }

    status_value = task.get("status", "unknown")
    status_text = _STATUS_TEXT.get(status_value, f"Status: {status_value}")

    # Build next actions based on status
    next_actions = []
    if status_value in ("pending_delivery", "delivered", "pending_accept", "accepted", "in_progress"):
        next_actions.append("get_task")  # Poll again
    if status_value == "waiting_human_confirm":
        next_actions.append("confirm_human")
    if status_value == "completed":
        next_actions.append("search_agents")  # Find another agent

    task_data = {
        "task_id": task.get("id"),
        "from_agent_id": task.get("from_agent_id"),
        "to_agent_id": task.get("to_agent_id"),
        "task_type": task.get("task_type"),
        "description": task.get("description"),
        "status": status_value,
        "risk_level": task.get("risk_level"),
        "requires_human_confirm": task.get("requires_human_confirm", False),
        "created_at": task.get("created_at"),
        "completed_at": task.get("completed_at"),
    }

    # Include approval URL if waiting for confirm
    approval_url = task.get("approval_url")
    fallback_url = approval_url or f"{settings.FALLBACK_BASE_URL}/tasks/{req.task_id}"

    return {
        "summary_text": f"Task {req.task_id}: {status_text}",
        "data": task_data,
        "next_actions": next_actions,
        "fallback_url": fallback_url,
    }


@router.get("/get_task/schema")
async def get_task_schema():
    """Return the MCP tool schema for get_task."""
    return TOOL_SCHEMA
