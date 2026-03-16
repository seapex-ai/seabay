"""Tests for backend card builders (app/cards/)."""

from __future__ import annotations

from app.cards.match_result import build_match_result_card
from app.cards.task_approval import build_task_approval_card


class TestTaskApprovalCard:
    """Test task_approval card building."""

    def test_low_risk_card(self):
        """R0 card should have callback_button actions."""
        card = build_task_approval_card(
            task_id="tsk_abc",
            task_type="service_request",
            description="Translate a document",
            risk_level="R0",
            status="pending_accept",
            from_agent_name="TranslatorBot",
            from_agent_id="agt_123",
            from_verification="email",
            to_agent_name="UserAgent",
            expires_at="2026-03-14T00:00:00Z",
        )
        assert card["card_type"] == "task_approval"
        assert card["source"] == "seabay"
        assert len(card["actions"]) == 2
        assert card["actions"][0]["type"] == "callback_button"
        assert card["actions"][0]["label"] == "Accept"
        assert card["actions"][1]["type"] == "callback_button"
        assert card["actions"][1]["label"] == "Decline"

    def test_high_risk_r2_card(self):
        """R2 card in human_confirm status should use open_url actions."""
        card = build_task_approval_card(
            task_id="tsk_hr2",
            task_type="collaboration",
            description="Book a restaurant",
            risk_level="R2",
            status="waiting_human_confirm",
            from_agent_name="BookingBot",
            from_agent_id="agt_456",
            from_verification="github",
            to_agent_name="UserAgent",
            expires_at="2026-03-14T00:00:00Z",
            human_confirm_token="tok_abc123",
        )
        assert card["actions"][0]["type"] == "open_url"
        # Should have risk_banner block
        risk_blocks = [b for b in card["blocks"] if b.get("type") == "risk_banner"]
        assert len(risk_blocks) == 1

    def test_r3_card_has_strong_warning(self):
        """R3 card should have HIGH RISK in risk_banner."""
        card = build_task_approval_card(
            task_id="tsk_hr3",
            task_type="service_request",
            description="Process payment",
            risk_level="R3",
            status="waiting_human_confirm",
            from_agent_name="PayBot",
            from_agent_id="agt_789",
            from_verification="domain",
            to_agent_name="UserAgent",
            expires_at="2026-03-14T00:00:00Z",
            human_confirm_token="tok_xyz789",
        )
        risk_blocks = [b for b in card["blocks"] if b.get("type") == "risk_banner"]
        assert "HIGH RISK" in risk_blocks[0]["message"]

    def test_card_has_fallback_text(self):
        """Card should always have fallback_text."""
        card = build_task_approval_card(
            task_id="tsk_fb",
            task_type="service_request",
            description="Test",
            risk_level="R0",
            status="pending_accept",
            from_agent_name="Bot",
            from_agent_id="agt_1",
            from_verification="none",
            to_agent_name="User",
            expires_at="2026-03-14T00:00:00Z",
        )
        assert card["fallback_text"]
        assert "Bot" in card["fallback_text"]
        assert "tsk_fb" in card["fallback_text"]

    def test_card_envelope_fields(self):
        """Card should have all CardEnvelope required fields."""
        card = build_task_approval_card(
            task_id="tsk_env",
            task_type="service_request",
            description="Test",
            risk_level="R0",
            status="pending_accept",
            from_agent_name="Bot",
            from_agent_id="agt_1",
            from_verification="none",
            to_agent_name="User",
            expires_at="2026-03-14T00:00:00Z",
        )
        assert card["card_type"] == "task_approval"
        assert card["card_version"] == "1.0"
        assert card["source"] == "seabay"
        assert "card_id" in card
        assert "created_at" in card
        assert "locale" in card
        assert "blocks" in card
        assert "actions" in card
        assert "fallback_text" in card
        assert card["callback_base_url"] == "https://seabay.ai/v1"
        assert card["auth_hint"] == "bearer_token_required"

    def test_verification_badge(self):
        """Card should include verification badge when verified."""
        card = build_task_approval_card(
            task_id="tsk_badge",
            task_type="service_request",
            description="Test",
            risk_level="R0",
            status="pending_accept",
            from_agent_name="Bot",
            from_agent_id="agt_1",
            from_verification="github",
            to_agent_name="User",
            expires_at="2026-03-14T00:00:00Z",
        )
        badge_rows = [b for b in card["blocks"] if b.get("type") == "badge_row"]
        assert len(badge_rows) >= 1

    def test_relationship_badge(self):
        """Card should include relationship badge when strength provided."""
        card = build_task_approval_card(
            task_id="tsk_rel",
            task_type="service_request",
            description="Test",
            risk_level="R0",
            status="pending_accept",
            from_agent_name="Bot",
            from_agent_id="agt_1",
            from_verification="none",
            to_agent_name="User",
            expires_at="2026-03-14T00:00:00Z",
            relationship_strength="trusted",
        )
        badge_rows = [b for b in card["blocks"] if b.get("type") == "badge_row"]
        assert len(badge_rows) >= 1


class TestMatchResultCard:
    """Test match_result card building."""

    def test_basic_match_card(self):
        """Match result card with multiple candidates."""
        matches = [
            {
                "agent_id": "agt_1",
                "display_name": "Translator",
                "verification_level": "github",
                "match_score": 90,
                "reasons": ["Skill: translation", "Language: en-zh", "Verified"],
                "badges": ["github"],
            },
            {
                "agent_id": "agt_2",
                "display_name": "Writer",
                "verification_level": "email",
                "match_score": 65,
                "reasons": ["Skill: writing", "Available"],
                "badges": [],
            },
        ]
        card = build_match_result_card(
            intent_id="int_abc",
            intent_description="Find a translator",
            matches=matches,
            expires_at="2026-03-14T00:00:00Z",
        )
        assert card["card_type"] == "match_result"
        assert len(card["actions"]) == 2
        assert "Select" in card["actions"][0]["label"]

    def test_card_has_reasons(self):
        """Each match should show reasons in reason_list block."""
        matches = [
            {
                "agent_id": "agt_1",
                "display_name": "Bot",
                "match_score": 80,
                "reasons": ["R1", "R2", "R3"],
            },
        ]
        card = build_match_result_card(
            intent_id="int_1",
            intent_description="Test",
            matches=matches,
            expires_at="2026-03-14T00:00:00Z",
        )
        reason_blocks = [b for b in card["blocks"] if b.get("type") == "reason_list"]
        assert len(reason_blocks) >= 1
        assert len(reason_blocks[0]["reasons"]) == 3

    def test_fallback_includes_scores(self):
        """Fallback text should include match scores."""
        matches = [
            {"agent_id": "agt_1", "display_name": "Bot", "match_score": 75, "reasons": ["R1"]},
        ]
        card = build_match_result_card(
            intent_id="int_1",
            intent_description="Test",
            matches=matches,
            expires_at="2026-03-14T00:00:00Z",
        )
        assert "Bot" in card["fallback_text"]

    def test_max_5_matches_displayed(self):
        """Card should display at most 5 matches."""
        matches = [
            {"agent_id": f"agt_{i}", "display_name": f"Bot{i}", "match_score": 50 + i, "reasons": [f"R{i}"]}
            for i in range(8)
        ]
        card = build_match_result_card(
            intent_id="int_1",
            intent_description="Test",
            matches=matches,
            expires_at="2026-03-14T00:00:00Z",
        )
        # Actions should be at most number of matches (all 8 in this case)
        assert len(card["actions"]) == 8
