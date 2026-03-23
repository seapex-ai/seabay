"""Task Receipt Card builder — per Freeze Pack #4 contract."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.id_generator import generate_id


def build_receipt_card(
    task_id: str,
    task_type: str,
    description: str | None,
    risk_level: str,
    from_agent_name: str,
    from_agent_id: str,
    to_agent_name: str,
    to_agent_id: str,
    outcome: str,
    completed_at: str | None = None,
    duration_seconds: int | None = None,
    from_verification: str = "none",
    to_verification: str = "none",
) -> dict:
    """Build a Task Receipt Card JSON per V1.5 Lite contract.

    Issued after a task reaches a terminal state (completed, failed, declined, cancelled).
    """
    card_id = generate_id("card")
    is_success = outcome == "completed"

    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": "Task Completed" if is_success else f"Task {outcome.replace('_', ' ').title()}",
    })

    # Outcome banner
    if is_success:
        blocks.append({
            "type": "status_banner",
            "status": "success",
            "message": "This task has been completed successfully.",
        })
    else:
        blocks.append({
            "type": "status_banner",
            "status": outcome,
            "message": f"This task was {outcome}.",
        })

    # Participants
    blocks.append({
        "type": "section",
        "text": "Participants",
        "fields": [
            {"label": "Requester", "value": from_agent_name},
            {"label": "Provider", "value": to_agent_name},
        ],
    })

    # Task details
    fields = [
        {"label": "Type", "value": task_type},
        {"label": "Risk Level", "value": risk_level},
        {"label": "Outcome", "value": outcome},
    ]
    if completed_at:
        fields.append({"label": "Completed At", "value": completed_at})
    if duration_seconds is not None:
        mins = duration_seconds // 60
        fields.append({"label": "Duration", "value": f"{mins}m" if mins > 0 else f"{duration_seconds}s"})
    blocks.append({
        "type": "section",
        "text": description or "No description provided",
        "fields": fields,
    })

    # Badge row
    badges = []
    if from_verification != "none":
        badges.append({"type": "verification", "label": f"Requester: {from_verification}"})
    if to_verification != "none":
        badges.append({"type": "verification", "label": f"Provider: {to_verification}"})
    if badges:
        blocks.append({"type": "badge_row", "badges": badges})

    # Context
    blocks.append({
        "type": "context",
        "text": f"Task ID: {task_id}",
    })

    # Fallback text
    fallback = (
        f"**Task Receipt — {outcome.title()}**\n\n"
        f"**From:** {from_agent_name}\n"
        f"**To:** {to_agent_name}\n"
        f"**Type:** {task_type} | **Risk:** {risk_level}\n"
        f"**Task:** {description or 'N/A'}\n"
        f"**Outcome:** {outcome}\n"
    )
    if completed_at:
        fallback += f"**Completed:** {completed_at}\n"
    fallback += f"\n_Task ID: {task_id}_"

    return {
        "card_type": "receipt",
        "card_version": "1.0",
        "card_id": card_id,
        "source": "seabay",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "locale": "en",
        "blocks": blocks,
        "actions": [],
        "fallback_text": fallback,
    }
