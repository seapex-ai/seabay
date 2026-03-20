"""A2A (Agent-to-Agent) Protocol Adapter.

Translates between Seabay internal format and the open A2A protocol.
Reference: Google A2A specification.

Key mappings:
- A2A Agent Card ↔ Seabay Agent + Profile
- A2A Task states ↔ Seabay 12-state machine
- A2A Message parts ↔ Seabay payload_inline / description

Frozen Principle: A2A aligned — Seabay follows A2A conventions
but extends with risk levels, human-confirm, and trust signals.
"""

from __future__ import annotations

from typing import Any, Optional


# ── Agent Card Conversion ──

def agent_to_a2a_card(agent: dict, profile: Optional[dict] = None) -> dict:
    """Convert Seabay agent data to A2A Agent Card format.

    A2A Agent Card is the standard discovery format for machine-readable
    agent metadata, served at /.well-known/agent-card/{id}.json
    """
    skills = profile.get("skills", []) if profile else []
    languages = profile.get("languages", []) if profile else []
    can_offer = profile.get("can_offer", []) if profile else []

    card = {
        "name": agent.get("display_name"),
        "description": profile.get("bio") if profile else None,
        "url": f"https://seabay.ai/agents/{agent.get('slug')}",
        "provider": {
            "organization": "Seabay",
            "url": "https://seabay.ai",
        },
        "version": "1.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": True,
            "stateTransitionHistory": True,
        },
        "skills": [
            {"id": s, "name": s, "description": f"Skill: {s}"}
            for s in skills
        ],
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "authentication": {
            "schemes": ["bearer"],
        },
    }

    # Add extended metadata (Seabay specific)
    card["x-seabay"] = {
        "agent_id": agent.get("id"),
        "agent_type": agent.get("agent_type"),
        "verification_level": agent.get("verification_level", "none"),
        "contact_policy": agent.get("contact_policy"),
        "visibility_scope": agent.get("visibility_scope"),
        "status": agent.get("status"),
        "languages": languages,
        "can_offer": can_offer,
        "risk_capabilities": profile.get("risk_capabilities", []) if profile else [],
        "region": agent.get("region", "intl"),
    }

    return card


def a2a_card_to_agent(card: dict) -> dict:
    """Convert A2A Agent Card to Seabay registration-compatible dict."""
    skills = [s.get("id", s.get("name", "")) for s in card.get("skills", [])]
    ext = card.get("x-seabay", {})

    return {
        "display_name": card.get("name", "Unknown"),
        "agent_type": ext.get("agent_type", "service"),
        "endpoint": card.get("url"),
        "bio": card.get("description"),
        "skills": skills,
        "languages": ext.get("languages", []),
    }


# ── Task State Mapping ──

# Seabay → A2A state mapping
_STATUS_TO_A2A = {
    "draft": "submitted",
    "pending_delivery": "submitted",
    "delivered": "submitted",
    "pending_accept": "working",
    "accepted": "working",
    "in_progress": "working",
    "waiting_human_confirm": "input-required",
    "completed": "completed",
    "declined": "canceled",
    "expired": "canceled",
    "cancelled": "canceled",
    "failed": "failed",
}

# A2A → Seabay state mapping (best effort)
_A2A_TO_STATUS = {
    "submitted": "pending_delivery",
    "working": "in_progress",
    "input-required": "waiting_human_confirm",
    "completed": "completed",
    "canceled": "cancelled",
    "failed": "failed",
}


def internal_task_to_a2a(task: dict) -> dict:
    """Convert Seabay Task to A2A Task response format.

    A2A Task format:
    {
      "id": "...",
      "status": {
        "state": "working|completed|...",
        "message": { "role": "agent", "parts": [...] }
      },
      "artifacts": [...]
    }
    """
    a2a_state = _STATUS_TO_A2A.get(task.get("status", ""), "unknown")

    parts = []
    if task.get("description"):
        parts.append({"type": "text", "text": task["description"]})

    result = {
        "id": task.get("id"),
        "status": {
            "state": a2a_state,
            "message": {
                "role": "agent",
                "parts": parts,
            },
        },
    }

    # Add artifacts if task has results
    if task.get("payload_inline"):
        result["artifacts"] = [{
            "name": "result",
            "parts": [{"type": "data", "data": task["payload_inline"]}],
        }]

    # Add extended metadata
    result["x-seabay"] = {
        "internal_status": task.get("status"),
        "risk_level": task.get("risk_level", "R0"),
        "requires_human_confirm": task.get("requires_human_confirm", False),
        "from_agent_id": task.get("from_agent_id"),
        "to_agent_id": task.get("to_agent_id"),
    }

    if a2a_state == "input-required" and task.get("approval_url"):
        result["status"]["message"]["parts"].append({
            "type": "text",
            "text": f"Human confirmation required: {task['approval_url']}",
        })

    return result


def a2a_task_to_internal(a2a_task: dict) -> dict:
    """Convert A2A Task format to Seabay Task creation request.

    Extracts text from message parts and maps metadata.
    """
    message = a2a_task.get("message", {})
    parts = message.get("parts", [])

    # Extract description from text parts
    description_parts = []
    payload_data = None
    for part in parts:
        if part.get("type") == "text":
            description_parts.append(part.get("text", ""))
        elif part.get("type") == "data":
            payload_data = part.get("data")

    description = "\n".join(description_parts) if description_parts else ""

    result = {
        "task_type": "service_request",
        "description": description,
        "risk_level": "R0",
    }

    if payload_data:
        result["payload_inline"] = payload_data

    # Map A2A metadata
    ext = a2a_task.get("x-seabay", {})
    if ext.get("risk_level"):
        result["risk_level"] = ext["risk_level"]
    if ext.get("task_type"):
        result["task_type"] = ext["task_type"]

    # Preserve A2A task ID for correlation
    result["metadata"] = {"a2a_task_id": a2a_task.get("id")}

    return result


def a2a_state_to_internal(a2a_state: str) -> str:
    """Map A2A task state to Seabay internal status."""
    return _A2A_TO_STATUS.get(a2a_state, "pending_delivery")


def internal_state_to_a2a(internal_status: str) -> str:
    """Map Seabay task status to A2A state."""
    return _STATUS_TO_A2A.get(internal_status, "unknown")


# ── A2A Message Helpers ──

def create_a2a_message(role: str, text: str, data: Any = None) -> dict:
    """Create an A2A-formatted message."""
    parts = [{"type": "text", "text": text}]
    if data is not None:
        parts.append({"type": "data", "data": data})
    return {"role": role, "parts": parts}


def extract_text_from_message(message: dict) -> str:
    """Extract all text from an A2A message's parts."""
    parts = message.get("parts", [])
    return "\n".join(
        part.get("text", "")
        for part in parts
        if part.get("type") == "text"
    )


def create_a2a_error(code: str, message: str) -> dict:
    """Create an A2A-formatted error response."""
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }
