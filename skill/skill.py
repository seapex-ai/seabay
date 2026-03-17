"""Seabay Skill — embedded module for agent frontend conversations.

This module handles:
1. Parsing text commands (accept, decline, confirm, reject, select, cancel)
2. Building structured cards (task_approval, match_result)
3. Rendering cards at appropriate level (plain text / markdown / structured JSON)
4. Executing API callbacks

Card system follows the CardEnvelope spec with blocks + actions.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional


# ── Text Command Parsing ──

COMMAND_PATTERNS = {
    "accept": re.compile(r"^accept\s+(tsk_\S+)$", re.IGNORECASE),
    "decline": re.compile(r"^decline\s+(tsk_\S+)(?:\s+(.+))?$", re.IGNORECASE),
    "confirm": re.compile(r"^confirm\s+(tsk_\S+)$", re.IGNORECASE),
    "reject": re.compile(r"^reject\s+(tsk_\S+)$", re.IGNORECASE),
    "select": re.compile(r"^select\s+(int_\S+)\s+(agt_\S+)$", re.IGNORECASE),
    "cancel": re.compile(r"^cancel\s+(tsk_\S+)(?:\s+(.+))?$", re.IGNORECASE),
    "complete": re.compile(r"^complete\s+(tsk_\S+)(?:\s+(\d(?:\.\d)?))?$", re.IGNORECASE),
    "inbox": re.compile(r"^inbox(?:\s+(\d+))?$", re.IGNORECASE),
    "status": re.compile(r"^status$", re.IGNORECASE),
}


def parse_command(text: str) -> Optional[dict]:
    """Parse user text input into a command action.

    Returns dict with 'action', 'method', 'path', 'body' or None if no match.
    """
    text = text.strip()
    for cmd, pattern in COMMAND_PATTERNS.items():
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groups()

        if cmd == "accept":
            return {"action": "accept", "method": "POST", "path": f"/tasks/{groups[0]}/accept", "body": {}}
        elif cmd == "decline":
            body = {"reason": groups[1]} if groups[1] else {}
            return {"action": "decline", "method": "POST", "path": f"/tasks/{groups[0]}/decline", "body": body}
        elif cmd == "confirm":
            return {"action": "confirm", "method": "POST", "path": f"/tasks/{groups[0]}/confirm-human", "body": {"confirmed": True}}
        elif cmd == "reject":
            return {"action": "reject", "method": "POST", "path": f"/tasks/{groups[0]}/confirm-human", "body": {"confirmed": False}}
        elif cmd == "select":
            return {"action": "select", "method": "POST", "path": f"/intents/{groups[0]}/select", "body": {"agent_id": groups[1]}}
        elif cmd == "cancel":
            body = {"reason": groups[1]} if groups[1] else {}
            return {"action": "cancel", "method": "POST", "path": f"/tasks/{groups[0]}/cancel", "body": body}
        elif cmd == "complete":
            body = {"rating": float(groups[1])} if groups[1] else {}
            return {"action": "complete", "method": "POST", "path": f"/tasks/{groups[0]}/complete", "body": body}
        elif cmd == "inbox":
            limit = int(groups[0]) if groups[0] else 20
            return {"action": "inbox", "method": "GET", "path": "/tasks/inbox", "body": {}, "params": {"limit": limit}}
        elif cmd == "status":
            return {"action": "status", "method": "GET", "path": "/health", "body": {}}

    return None


# ── Card Building ──

def build_task_approval_card(
    task: dict,
    from_agent: dict,
    callback_base_url: str = "https://seabay.ai/v1",
) -> dict:
    """Build a task_approval card for the recipient to accept/decline.

    Follows the CardEnvelope spec with blocks and actions.
    """
    risk_level = task.get("risk_level", "R0")
    task_id = task.get("id", "")
    task_type = task.get("task_type", "service_request")
    description = task.get("description", "")

    blocks = [
        {"type": "header", "text": f"New Task: {task_type.replace('_', ' ').title()}"},
        {"type": "section", "text": description[:500], "fields": [
            {"label": "From", "value": from_agent.get("display_name", "Unknown")},
            {"label": "Type", "value": task_type},
            {"label": "Risk Level", "value": risk_level},
        ]},
    ]

    if risk_level in ("R2", "R3"):
        risk_messages = {
            "R2": "This task requires human confirmation before proceeding.",
            "R3": "HIGH RISK: This task requires strong human confirmation.",
        }
        blocks.append({"type": "risk_banner", "risk_level": risk_level, "message": risk_messages[risk_level]})

    blocks.append({"type": "agent_summary",
        "agent_id": from_agent.get("id", ""),
        "name": from_agent.get("display_name", "Unknown"),
        "agent_type": from_agent.get("agent_type", "personal"),
        "verification_level": from_agent.get("verification_level", "none"),
        "status": from_agent.get("status", "online"),
    })

    if task.get("expires_at"):
        blocks.append({"type": "context", "text": f"Expires: {task['expires_at']}"})

    actions = [
        {
            "type": "callback_button",
            "label": "Accept",
            "style": "primary",
            "callback_method": "POST",
            "callback_path": f"/tasks/{task_id}/accept",
            "callback_body": {},
        },
        {
            "type": "callback_button",
            "label": "Decline",
            "style": "danger",
            "callback_method": "POST",
            "callback_path": f"/tasks/{task_id}/decline",
            "callback_body": {},
            "confirm": {
                "title": "Decline Task",
                "text": "Are you sure you want to decline this task?",
                "confirm_label": "Decline",
                "cancel_label": "Cancel",
            },
        },
    ]

    fallback = f"**New Task from {from_agent.get('display_name', 'Unknown')}**\n"
    fallback += f"Type: {task_type} | Risk: {risk_level}\n"
    fallback += f"{description[:200]}\n"
    fallback += f"Reply: `accept {task_id}` or `decline {task_id}`"

    now = datetime.now(timezone.utc)
    return {
        "card_type": "task_approval",
        "card_version": "1.0",
        "card_id": task_id,
        "source": "seabay",
        "created_at": now.isoformat(),
        "expires_at": task.get("expires_at", ""),
        "locale": "en",
        "blocks": blocks,
        "actions": actions,
        "fallback_text": fallback,
        "callback_base_url": callback_base_url,
        "auth_hint": "bearer",
    }


def build_match_result_card(
    intent: dict,
    matches: list[dict],
    callback_base_url: str = "https://seabay.ai/v1",
) -> dict:
    """Build a match_result card showing intent matching candidates."""
    intent_id = intent.get("id", "")
    description = intent.get("description", "")

    blocks = [
        {"type": "header", "text": "Match Results"},
        {"type": "section", "text": f"Intent: {description[:200]}"},
        {"type": "divider"},
    ]

    for i, match in enumerate(matches[:5], 1):
        blocks.append({"type": "agent_summary",
            "agent_id": match.get("agent_id", ""),
            "name": match.get("display_name", "Unknown"),
            "agent_type": match.get("agent_type", "service"),
            "verification_level": match.get("verification_level", "none"),
            "status": "online",
        })
        if match.get("reasons"):
            blocks.append({"type": "reason_list", "reasons": match["reasons"][:3]})
        blocks.append({"type": "key_value", "key": "Score", "value": str(match.get("match_score", 0))})
        if match.get("badges"):
            blocks.append({"type": "badge_row", "badges": [
                {"type": b, "label": b.replace("_", " ").title()} for b in match["badges"]
            ]})
        if i < len(matches):
            blocks.append({"type": "divider"})

    actions = []
    for match in matches[:5]:
        actions.append({
            "type": "callback_button",
            "label": f"Select {match.get('display_name', 'Agent')[:20]}",
            "style": "primary",
            "callback_method": "POST",
            "callback_path": f"/intents/{intent_id}/select",
            "callback_body": {"agent_id": match.get("agent_id")},
        })

    # Build fallback text
    fallback = f"**{len(matches)} matches found for your intent**\n\n"
    for i, match in enumerate(matches[:5], 1):
        fallback += f"{i}. **{match.get('display_name')}** (score: {match.get('match_score', 0)})\n"
        for reason in match.get("reasons", [])[:3]:
            fallback += f"   - {reason}\n"
    fallback += f"\nReply: `select {intent_id} <agent_id>` to choose"

    now = datetime.now(timezone.utc)
    return {
        "card_type": "match_result",
        "card_version": "1.0",
        "card_id": intent_id,
        "source": "seabay",
        "created_at": now.isoformat(),
        "expires_at": intent.get("expires_at", ""),
        "locale": "en",
        "blocks": blocks,
        "actions": actions,
        "fallback_text": fallback,
        "callback_base_url": callback_base_url,
        "auth_hint": "bearer",
    }


def build_human_confirm_card(
    task: dict,
    approval_url: str,
    callback_base_url: str = "https://seabay.ai/v1",
) -> dict:
    """Build a human confirmation card for R2/R3 tasks."""
    task_id = task.get("id", "")
    risk_level = task.get("risk_level", "R2")

    timeout_hours = 4 if risk_level == "R2" else 12

    blocks = [
        {"type": "header", "text": f"Human Confirmation Required ({risk_level})"},
        {"type": "risk_banner", "risk_level": risk_level,
         "message": f"This action requires your explicit confirmation within {timeout_hours} hours."},
        {"type": "section", "text": task.get("description", ""), "fields": [
            {"label": "Task ID", "value": task_id},
            {"label": "Risk Level", "value": risk_level},
            {"label": "Timeout", "value": f"{timeout_hours} hours"},
        ]},
    ]

    actions = [
        {
            "type": "callback_button",
            "label": "Approve",
            "style": "primary",
            "callback_method": "POST",
            "callback_path": f"/tasks/{task_id}/confirm-human",
            "callback_body": {"confirmed": True},
            "confirm": {
                "title": "Confirm Action",
                "text": f"You are approving a {risk_level} risk action. This cannot be undone.",
                "confirm_label": "Yes, Approve",
                "cancel_label": "Cancel",
            },
        },
        {
            "type": "callback_button",
            "label": "Deny",
            "style": "danger",
            "callback_method": "POST",
            "callback_path": f"/tasks/{task_id}/confirm-human",
            "callback_body": {"confirmed": False},
        },
        {
            "type": "open_url",
            "label": "Open in Browser",
            "url": approval_url,
            "style": "default",
        },
    ]

    fallback = f"**{risk_level} Confirmation Required**\n"
    fallback += f"{task.get('description', '')[:200]}\n"
    fallback += f"Approve: {approval_url}\n"
    fallback += f"Reply: `confirm {task_id}` or `reject {task_id}`"

    now = datetime.now(timezone.utc)
    return {
        "card_type": "task_approval",
        "card_version": "1.0",
        "card_id": task_id,
        "source": "seabay",
        "created_at": now.isoformat(),
        "expires_at": task.get("human_confirm_deadline", ""),
        "locale": "en",
        "blocks": blocks,
        "actions": actions,
        "fallback_text": fallback,
        "callback_base_url": callback_base_url,
        "auth_hint": "bearer",
    }


# ── Card Rendering ──

def render_card(card: dict, level: int = 1) -> Any:
    """Render a card at the specified level.

    Level 0: Plain text (strip markdown)
    Level 1: Markdown (use fallback_text)
    Level 2: Return JSON as-is (host renders structured blocks)
    """
    if level == 0:
        text = card.get("fallback_text", "")
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"_(.*?)_", r"\1", text)
        text = re.sub(r"`(.*?)`", r"\1", text)
        return text
    elif level == 1:
        return card.get("fallback_text", "No content available")
    else:
        return card


def should_render_card(card: dict) -> bool:
    """Check if the card has not expired."""
    expires_at = card.get("expires_at")
    if not expires_at:
        return True
    try:
        exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < exp
    except (ValueError, TypeError):
        return True


def extract_actions(card: dict) -> list[dict]:
    """Extract available actions from a card."""
    return card.get("actions", [])


def get_callback_buttons(card: dict) -> list[dict]:
    """Get only callback_button actions from a card."""
    return [a for a in card.get("actions", []) if a.get("type") == "callback_button"]
