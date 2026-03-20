"""Tests for the Skill module — command parsing, card building, rendering."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skill"))

from skill import (
    build_human_confirm_card,
    build_match_result_card,
    build_task_approval_card,
    extract_actions,
    get_callback_buttons,
    parse_command,
    render_card,
    should_render_card,
)


class TestParseCommand:
    def test_accept(self):
        cmd = parse_command("accept tsk_abc123")
        assert cmd is not None
        assert cmd["action"] == "accept"
        assert cmd["method"] == "POST"
        assert "/tasks/tsk_abc123/accept" in cmd["path"]

    def test_decline(self):
        cmd = parse_command("decline tsk_xyz456")
        assert cmd["action"] == "decline"
        assert "/tasks/tsk_xyz456/decline" in cmd["path"]

    def test_decline_with_reason(self):
        cmd = parse_command("decline tsk_xyz Too busy right now")
        assert cmd["action"] == "decline"
        assert cmd["body"]["reason"] == "Too busy right now"

    def test_confirm(self):
        cmd = parse_command("confirm tsk_abc123")
        assert cmd["action"] == "confirm"
        assert cmd["body"]["confirmed"] is True

    def test_reject(self):
        cmd = parse_command("reject tsk_abc123")
        assert cmd["action"] == "reject"
        assert cmd["body"]["confirmed"] is False

    def test_select(self):
        cmd = parse_command("select int_abc123 agt_xyz456")
        assert cmd["action"] == "select"
        assert cmd["body"]["agent_id"] == "agt_xyz456"
        assert "/intents/int_abc123/select" in cmd["path"]

    def test_cancel(self):
        cmd = parse_command("cancel tsk_abc123")
        assert cmd["action"] == "cancel"

    def test_complete(self):
        cmd = parse_command("complete tsk_abc123 4.5")
        assert cmd["action"] == "complete"
        assert cmd["body"]["rating"] == 4.5

    def test_complete_no_rating(self):
        cmd = parse_command("complete tsk_abc123")
        assert cmd["action"] == "complete"
        assert cmd["body"] == {}

    def test_inbox(self):
        cmd = parse_command("inbox")
        assert cmd["action"] == "inbox"
        assert cmd["method"] == "GET"

    def test_inbox_with_limit(self):
        cmd = parse_command("inbox 50")
        assert cmd["params"]["limit"] == 50

    def test_status(self):
        cmd = parse_command("status")
        assert cmd["action"] == "status"

    def test_no_match(self):
        assert parse_command("hello world") is None
        assert parse_command("") is None

    def test_case_insensitive(self):
        cmd = parse_command("ACCEPT tsk_abc123")
        assert cmd is not None
        assert cmd["action"] == "accept"

    def test_whitespace_handling(self):
        cmd = parse_command("  accept tsk_abc123  ")
        assert cmd is not None


class TestBuildTaskApprovalCard:
    def test_basic_card(self):
        task = {
            "id": "tsk_123",
            "task_type": "service_request",
            "description": "Translate this document",
            "risk_level": "R0",
        }
        agent = {"id": "agt_1", "display_name": "Test Agent", "agent_type": "personal"}

        card = build_task_approval_card(task, agent)
        assert card["card_type"] == "task_approval"
        assert card["card_id"] == "tsk_123"
        assert card["source"] == "seabay"
        assert len(card["blocks"]) >= 2
        assert len(card["actions"]) == 2
        assert "accept" in card["actions"][0]["callback_path"]
        assert "decline" in card["actions"][1]["callback_path"]

    def test_high_risk_card(self):
        task = {"id": "tsk_hr", "task_type": "collaboration", "description": "Payment", "risk_level": "R3"}
        agent = {"display_name": "Test"}

        card = build_task_approval_card(task, agent)
        risk_banners = [b for b in card["blocks"] if b.get("type") == "risk_banner"]
        assert len(risk_banners) == 1
        assert risk_banners[0]["risk_level"] == "R3"

    def test_fallback_text(self):
        task = {"id": "tsk_1", "task_type": "service_request", "description": "Test", "risk_level": "R0"}
        agent = {"display_name": "Bot"}

        card = build_task_approval_card(task, agent)
        assert "Bot" in card["fallback_text"]
        assert "tsk_1" in card["fallback_text"]


class TestBuildMatchResultCard:
    def test_basic_card(self):
        intent = {"id": "int_1", "description": "Find translator"}
        matches = [
            {
                "agent_id": "agt_1", "display_name": "Translator",
                "match_score": 90, "reasons": ["Skill match"], "badges": ["github"],
            },
            {
                "agent_id": "agt_2", "display_name": "Writer",
                "match_score": 60, "reasons": ["Language match"], "badges": [],
            },
        ]

        card = build_match_result_card(intent, matches)
        assert card["card_type"] == "match_result"
        assert card["card_id"] == "int_1"
        assert len(card["actions"]) == 2

    def test_fallback_includes_scores(self):
        intent = {"id": "int_1", "description": "Test"}
        matches = [{"agent_id": "agt_1", "display_name": "Bot", "match_score": 75, "reasons": ["R1"], "badges": []}]

        card = build_match_result_card(intent, matches)
        assert "75" in card["fallback_text"]
        assert "Bot" in card["fallback_text"]


class TestBuildHumanConfirmCard:
    def test_r2_card(self):
        task = {"id": "tsk_hc", "description": "Book restaurant", "risk_level": "R2"}
        card = build_human_confirm_card(task, "https://seabay.ai/approve/tok1")
        assert "4 hours" in card["blocks"][1]["message"]
        assert len(card["actions"]) == 3  # approve, deny, open_url

    def test_r3_card(self):
        task = {"id": "tsk_hc", "description": "Payment", "risk_level": "R3"}
        card = build_human_confirm_card(task, "https://seabay.ai/approve/tok2")
        assert "12 hours" in card["blocks"][1]["message"]

    def test_open_url_action(self):
        task = {"id": "tsk_1", "risk_level": "R2"}
        url = "https://seabay.ai/approve/token123"
        card = build_human_confirm_card(task, url)
        url_actions = [a for a in card["actions"] if a.get("type") == "open_url"]
        assert len(url_actions) == 1
        assert url_actions[0]["url"] == url


class TestRenderCard:
    def test_level_0_plain_text(self):
        card = {"fallback_text": "**Bold** and _italic_ and `code`"}
        result = render_card(card, level=0)
        assert "**" not in result
        assert "_" not in result
        assert "`" not in result
        assert "Bold" in result

    def test_level_1_markdown(self):
        card = {"fallback_text": "**Bold** text"}
        result = render_card(card, level=1)
        assert "**Bold**" in result

    def test_level_2_json(self):
        card = {"card_type": "task_approval", "blocks": []}
        result = render_card(card, level=2)
        assert result == card


class TestShouldRenderCard:
    def test_no_expiry(self):
        assert should_render_card({}) is True

    def test_future_expiry(self):
        from datetime import datetime, timedelta, timezone
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert should_render_card({"expires_at": future}) is True

    def test_past_expiry(self):
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert should_render_card({"expires_at": past}) is False


class TestCardHelpers:
    def test_extract_actions(self):
        card = {"actions": [{"type": "callback_button"}, {"type": "open_url"}]}
        assert len(extract_actions(card)) == 2

    def test_get_callback_buttons(self):
        card = {"actions": [
            {"type": "callback_button", "label": "Accept"},
            {"type": "open_url", "label": "View"},
            {"type": "callback_button", "label": "Decline"},
        ]}
        buttons = get_callback_buttons(card)
        assert len(buttons) == 2
        assert buttons[0]["label"] == "Accept"
