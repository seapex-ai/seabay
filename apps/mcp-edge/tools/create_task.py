"""P0 Tool: create_task — send a task to a target agent.

Risk level: R1-R3 (determined by intent content)
Auth: OAuth required

When risk is R2/R3, the tool does NOT execute directly but returns
an approval object requiring human confirmation via confirm_human.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from config import settings
from auth.oauth import require_scope
from auth.jwt import create_core_auth_header
from middleware.risk_gate import check_risk, assess_risk_level

logger = logging.getLogger("mcp-edge.tools.create_task")

router = APIRouter()

TOOL_SCHEMA = {
    "name": "create_task",
    "description": (
        "Create and send a task to a specific agent. Use this after finding "
        "a suitable agent via search_agents. The task will be delivered to the "
        "target agent's inbox. High-risk tasks (involving payments, personal "
        "contact, etc.) will require human confirmation before execution."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["to_agent_id", "task_type", "description"],
        "properties": {
            "to_agent_id": {
                "type": "string",
                "description": "Target agent ID",
            },
            "task_type": {
                "type": "string",
                "enum": ["service_request", "collaboration", "introduction"],
                "description": "Type of task",
            },
            "description": {
                "type": "string",
                "description": "What you need the agent to do",
            },
            "payload_inline": {
                "type": "object",
                "description": "Additional structured data for the task (optional, < 1KB)",
            },
            "idempotency_key": {
                "type": "string",
                "description": "Client-generated unique key for deduplication",
            },
        },
    },
}


class CreateTaskInput(BaseModel):
    to_agent_id: str
    task_type: str = "service_request"
    description: str = Field(..., min_length=1, max_length=2000)
    payload_inline: dict | None = None
    idempotency_key: str | None = None


@router.post("/create_task")
async def create_task(
    req: CreateTaskInput,
    request: Request,
    auth: dict = Depends(require_scope("task.create")),
):
    """Execute create_task tool — R1-R3, OAuth required.

    Assesses risk level from task description, then either:
    - R0/R1: Creates task directly via Core API
    - R2/R3: Returns approval_required response with confirm flow
    """
    # Assess risk level from description
    risk_level = assess_risk_level(req.description)

    # If R2/R3, return approval object instead of executing
    if risk_level in ("R2", "R3"):
        approval_id = f"apv_{secrets.token_urlsafe(16)}"
        return {
            "summary_text": (
                f"This task requires your confirmation before sending (risk level: {risk_level})."
            ),
            "data": {
                "status": "approval_required",
                "task_preview": {
                    "to_agent_id": req.to_agent_id,
                    "task_type": req.task_type,
                    "description": req.description,
                    "risk_level": risk_level,
                },
                "approval": {
                    "approval_id": approval_id,
                    "title": "Confirm task creation",
                    "summary": f"You are about to send a {req.task_type} to agent {req.to_agent_id}.",
                    "actions": ["approve", "reject", "approve_once"],
                    "fallback_url": f"{settings.FALLBACK_BASE_URL}/approvals/{approval_id}",
                    "expires_in": 14400 if risk_level == "R2" else 43200,
                },
            },
            "next_actions": ["confirm_human"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/approvals/{approval_id}",
        }

    # R0/R1 — create task via Core API
    check_risk(risk_level, tool_name="create_task")

    # Build Core API request
    task_body = {
        "to_agent_id": req.to_agent_id,
        "task_type": req.task_type,
        "description": req.description,
        "risk_level": risk_level,
        "idempotency_key": req.idempotency_key or secrets.token_urlsafe(16),
    }
    if req.payload_inline:
        task_body["payload_inline"] = req.payload_inline

    # Use internal JWT for Core API auth
    headers = create_core_auth_header(
        subject=auth["subject"],
        scopes=auth["scopes"],
        agent_id=auth.get("agent_id"),
    )

    core_client = request.app.state.core_client
    try:
        response = await core_client.post("/tasks", json=task_body, headers=headers)
        response.raise_for_status()
        task_data = response.json()
    except Exception as e:
        logger.error("Core API create_task failed: %s", e)
        return {
            "summary_text": "Failed to create the task. Please try again.",
            "data": {"error": str(e)},
            "next_actions": ["create_task"],
            "fallback_url": f"{settings.FALLBACK_BASE_URL}/tasks/new",
        }

    task_id = task_data.get("id", "")
    return {
        "summary_text": (
            f"Task created successfully and sent to agent {req.to_agent_id}. "
            f"Task ID: {task_id}. Status: {task_data.get('status', 'pending')}."
        ),
        "data": {
            "task_id": task_id,
            "to_agent_id": req.to_agent_id,
            "task_type": req.task_type,
            "status": task_data.get("status"),
            "risk_level": risk_level,
        },
        "next_actions": ["get_task"],
        "fallback_url": f"{settings.FALLBACK_BASE_URL}/tasks/{task_id}",
    }


@router.get("/create_task/schema")
async def create_task_schema():
    """Return the MCP tool schema for create_task."""
    return TOOL_SCHEMA
