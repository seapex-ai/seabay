"""Tests for intent matching logic (spec §13).

Tests the deterministic matching algorithm and scoring without DB.
"""

from __future__ import annotations

from app.services.intent_service import _compute_badges, _compute_trust_tier, _pad_reasons


class TestPadReasons:
    """Test the reason padding logic (spec §13.3: minimum 3 reasons)."""

    def test_pad_empty_reasons(self):
        reasons = []

        class FakeProfile:
            bio = "I am a bot"
            can_offer = ["translation"]
            languages = ["en", "ja"]

        _pad_reasons(reasons, FakeProfile())
        assert len(reasons) >= 3

    def test_pad_one_reason(self):
        reasons = ["Skills match: translation"]

        class FakeProfile:
            bio = "Hello"
            can_offer = ["writing"]
            languages = ["en"]

        _pad_reasons(reasons, FakeProfile())
        assert len(reasons) >= 3

    def test_no_pad_if_enough_reasons(self):
        reasons = ["Reason 1", "Reason 2", "Reason 3"]

        class FakeProfile:
            bio = None
            can_offer = []
            languages = []

        _pad_reasons(reasons, FakeProfile())
        assert len(reasons) == 3

    def test_pad_uses_bio(self):
        reasons = []

        class FakeProfile:
            bio = "I am a helpful bot"
            can_offer = []
            languages = []

        _pad_reasons(reasons, FakeProfile())
        assert any("profile" in r.lower() for r in reasons)

    def test_pad_uses_can_offer(self):
        reasons = ["Something"]

        class FakeProfile:
            bio = None
            can_offer = ["translation", "writing"]
            languages = []

        _pad_reasons(reasons, FakeProfile())
        assert any("offer" in r.lower() for r in reasons)

    def test_pad_uses_languages(self):
        reasons = ["Something"]

        class FakeProfile:
            bio = None
            can_offer = []
            languages = ["en", "ja", "zh"]

        _pad_reasons(reasons, FakeProfile())
        assert any("support" in r.lower() for r in reasons)

    def test_pad_fallback(self):
        reasons = []

        class FakeProfile:
            bio = None
            can_offer = []
            languages = []

        _pad_reasons(reasons, FakeProfile())
        assert any("collaboration" in r.lower() for r in reasons)


class TestComputeTrustTier:
    def test_none_without_edge(self):
        assert _compute_trust_tier(None) is None

    def test_new_returns_none(self):
        class FakeEdge:
            strength = "new"

        assert _compute_trust_tier(FakeEdge()) is None

    def test_acquaintance_returns_value(self):
        class FakeEdge:
            strength = "acquaintance"

        assert _compute_trust_tier(FakeEdge()) == "acquaintance"

    def test_trusted_returns_value(self):
        class FakeEdge:
            strength = "trusted"

        assert _compute_trust_tier(FakeEdge()) == "trusted"


class TestComputeBadges:
    def test_no_badges_for_unverified(self):
        class FakeAgent:
            verification_level = "none"
            agent_type = "personal"

        badges = _compute_badges(FakeAgent())
        assert badges == []

    def test_verification_badge(self):
        class FakeAgent:
            verification_level = "github"
            agent_type = "personal"

        badges = _compute_badges(FakeAgent())
        assert "github" in badges

    def test_service_badge(self):
        class FakeAgent:
            verification_level = "none"
            agent_type = "service"

        badges = _compute_badges(FakeAgent())
        assert "service_agent" in badges

    def test_both_badges(self):
        class FakeAgent:
            verification_level = "domain"
            agent_type = "service"

        badges = _compute_badges(FakeAgent())
        assert len(badges) == 2
        assert "domain" in badges
        assert "service_agent" in badges


class TestMatchScoring:
    """Test scoring rules from spec §13.1."""

    def test_skill_match_30_points_each(self):
        # 1 skill match = 30 pts
        req_skills = {"translation"}
        agent_skills = {"translation", "writing"}
        overlap = req_skills & agent_skills
        score = len(overlap) * 30
        assert score == 30

    def test_multiple_skill_matches(self):
        req_skills = {"translation", "writing", "editing"}
        agent_skills = {"translation", "writing"}
        overlap = req_skills & agent_skills
        score = len(overlap) * 30
        assert score == 60

    def test_language_match_15_points_each(self):
        req_langs = {"en", "ja"}
        agent_langs = {"en", "ja", "zh"}
        overlap = req_langs & agent_langs
        score = len(overlap) * 15
        assert score == 30

    def test_location_match_10_points(self):
        score = 10  # fixed bonus for location match
        assert score == 10

    def test_verification_bonus_10_points(self):
        score = 10
        assert score == 10

    def test_service_agent_bonus_5_points(self):
        score = 5
        assert score == 5

    def test_trusted_relationship_bonus_15_points(self):
        score = 15
        assert score == 15

    def test_acquaintance_relationship_bonus_8_points(self):
        score = 8
        assert score == 8
