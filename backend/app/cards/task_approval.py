"""Task Approval Card builder — per Freeze Pack #4 contract."""

from __future__ import annotations

from datetime import datetime

from app.core.id_generator import generate_id


def build_task_approval_card(
    task_id: str,
    task_type: str,
    description: str | None,
    risk_level: str,
    status: str,
    from_agent_name: str,
    from_agent_id: str,
    from_verification: str,
    to_agent_name: str,
    expires_at: str,
    relationship_strength: str | None = None,
    human_confirm_token: str | None = None,
) -> dict:
    """Build a Task Approval Card JSON per V1.5 Lite contract."""
    card_id = generate_id("card")
    is_high_risk = risk_level in ("R2", "R3")
    is_human_confirm = status == "waiting_human_confirm"

    blocks = []

    # Header
    if is_human_confirm:
        blocks.append({
            "type": "header",
            "text": "Human Confirmation Required",
        })
    else:
        blocks.append({
            "type": "header",
            "text": "New Task Request",
        })

    # Risk banner for R2/R3
    if is_high_risk:
        risk_msg = (
            "This action requires your explicit confirmation before execution. "
            "Please review carefully."
        )
        if risk_level == "R3":
            risk_msg = (
                "HIGH RISK: This action involves sensitive operations (payment, private data, etc). "
                "Strong confirmation required."
            )
        blocks.append({
            "type": "risk_banner",
            "risk_level": risk_level,
            "message": risk_msg,
        })

    # Agent summary
    blocks.append({
        "type": "agent_summary",
        "agent_id": from_agent_id,
        "name": from_agent_name,
        "agent_type": "service",
        "verification_level": from_verification,
        "status": "online",
    })

    # Task details section
    fields = [
        {"label": "Type", "value": task_type},
        {"label": "Risk Level", "value": risk_level},
        {"label": "Expires", "value": expires_at},
    ]
    blocks.append({
        "type": "section",
        "text": description or "No description provided",
        "fields": fields,
    })

    # Badge row
    badges = []
    if from_verification != "none":
        badges.append({"type": "verification", "label": from_verification})
    if relationship_strength:
        badges.append({"type": "relationship", "label": relationship_strength})
    if badges:
        blocks.append({"type": "badge_row", "badges": badges})

    # Context
    blocks.append({
        "type": "context",
        "text": f"Task ID: {task_id}",
    })

    # Actions
    actions = []
    if is_human_confirm:
        # R2/R3: open_url only, not callback_button
        actions.append({
            "type": "open_url",
            "label": "Review & Confirm",
            "url": f"https://seabay.ai/approve/{human_confirm_token}",
            "style": "primary",
        })
        actions.append({
            "type": "open_url",
            "label": "Reject",
            "url": f"https://seabay.ai/approve/{human_confirm_token}?action=reject",
            "style": "danger",
        })
    else:
        # Low-risk: callback_button
        actions.append({
            "type": "callback_button",
            "label": "Accept",
            "style": "primary",
            "callback_method": "POST",
            "callback_path": f"/tasks/{task_id}/accept",
            "callback_body": {},
        })
        actions.append({
            "type": "callback_button",
            "label": "Decline",
            "style": "danger",
            "callback_method": "POST",
            "callback_path": f"/tasks/{task_id}/decline",
            "callback_body": {},
            "confirm": {
                "title": "Decline Task?",
                "text": "Are you sure you want to decline this task?",
                "confirm_label": "Decline",
                "cancel_label": "Cancel",
            },
        })

    # Fallback text
    if is_human_confirm:
        fallback = (
            f"**Human Confirmation Required**\n\n"
            f"**Risk Level:** {risk_level}\n"
            f"**From:** {from_agent_name} ({from_verification})\n"
            f"**Task:** {description or 'N/A'}\n"
            f"**Expires:** {expires_at}\n\n"
            f"Review and confirm at: https://seabay.ai/approve/{human_confirm_token}\n\n"
            f"_Task ID: {task_id}_"
        )
    else:
        fallback = (
            f"**New Task Request**\n\n"
            f"**From:** {from_agent_name} ({from_verification})\n"
            f"**Type:** {task_type} | **Risk:** {risk_level}\n"
            f"**Task:** {description or 'N/A'}\n"
            f"**Expires:** {expires_at}\n\n"
            f"Reply: `accept {task_id}` or `decline {task_id}`\n\n"
            f"_Task ID: {task_id}_"
        )

    return {
        "card_type": "task_approval",
        "card_version": "1.0",
        "card_id": card_id,
        "source": "seabay",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "expires_at": expires_at,
        "locale": "en",
        "blocks": blocks,
        "actions": actions,
        "fallback_text": fallback,
        "callback_base_url": "https://seabay.ai/v1",
        "auth_hint": "bearer_token_required",
    }
