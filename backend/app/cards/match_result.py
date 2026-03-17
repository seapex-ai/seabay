"""Match Result Card builder — per Freeze Pack #4 contract."""

from __future__ import annotations

from datetime import datetime

from app.core.id_generator import generate_id


def build_match_result_card(
    intent_id: str,
    intent_description: str,
    matches: list[dict],
    expires_at: str,
) -> dict:
    """Build a Match Result Card JSON per V1.5 Lite contract.

    Each match dict should have:
        agent_id, display_name, verification_level, match_score,
        reasons (list[str], min 3), badges (list[str])
    """
    card_id = generate_id("card")
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": f"{len(matches)} Matches Found",
    })

    # Intent summary
    blocks.append({
        "type": "section",
        "text": intent_description,
    })

    # Each candidate
    actions = []
    for i, match in enumerate(matches):
        if i > 0:
            blocks.append({"type": "divider"})

        blocks.append({
            "type": "agent_summary",
            "agent_id": match["agent_id"],
            "name": match["display_name"],
            "agent_type": match.get("agent_type", "service"),
            "verification_level": match.get("verification_level", "none"),
            "status": "online",
        })

        blocks.append({
            "type": "reason_list",
            "reasons": match.get("reasons", ["Available for collaboration"])[:5],
        })

        badges = []
        if match.get("verification_level", "none") != "none":
            badges.append({"type": "verification", "label": match["verification_level"]})
        if match.get("trust_tier"):
            badges.append({"type": "trust", "label": match["trust_tier"]})
        if badges:
            blocks.append({"type": "badge_row", "badges": badges})

        actions.append({
            "type": "callback_button",
            "label": f"Select {match['display_name']}",
            "style": "primary",
            "callback_method": "POST",
            "callback_path": f"/intents/{intent_id}/select",
            "callback_body": {"agent_id": match["agent_id"]},
        })

    # Fallback text
    lines = [f"**{len(matches)} Matches Found**\n", f"_{intent_description}_\n"]
    for i, match in enumerate(matches, 1):
        reasons_str = "; ".join(match.get("reasons", [])[:3])
        lines.append(f"{i}. **{match['display_name']}** ({match.get('verification_level', 'none')}) — {reasons_str}")
    lines.append(f"\nReply: `select {intent_id} <agent_id>`")
    fallback = "\n".join(lines)

    return {
        "card_type": "match_result",
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
