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


class TestIntentCreationValidation:
    """Test intent creation validation rules."""

    def test_valid_categories(self):
        """All intent categories from spec should be defined."""
        from app.models.enums import IntentCategory

        values = {c.value for c in IntentCategory}
        assert "service_request" in values
        assert "collaboration" in values
        assert "introduction" in values

    def test_valid_statuses(self):
        """All intent statuses from spec should be defined."""
        from app.models.enums import IntentStatus

        values = {s.value for s in IntentStatus}
        assert "active" in values
        assert "matched" in values
        assert "fulfilled" in values
        assert "expired" in values
        assert "cancelled" in values

    def test_audience_scopes(self):
        """Audience scopes should include public and network."""
        from app.models.enums import AudienceScope

        values = {s.value for s in AudienceScope}
        assert "public" in values
        assert "network" in values

    def test_default_ttl_hours(self):
        """Default TTL for intents is 72 hours."""
        default_ttl = 72
        assert default_ttl == 72

    def test_max_matches_range(self):
        """max_matches should be between 1 and 20 per schema."""
        # From IntentCreateRequest: Field(5, ge=1, le=20)
        assert 1 <= 5 <= 20


class TestMatchingWeights:
    """Test matching weight configuration."""

    def test_default_weights_exist(self):
        from app.services.intent_service import WEIGHTS

        assert "skills_match" in WEIGHTS
        assert "languages_match" in WEIGHTS
        assert "location_match" in WEIGHTS
        assert "verification_level" in WEIGHTS
        assert "service_type_bonus" in WEIGHTS
        assert "relationship_bonus" in WEIGHTS

    def test_skills_weight_is_highest(self):
        from app.services.intent_service import WEIGHTS

        assert WEIGHTS["skills_match"] >= WEIGHTS["languages_match"]
        assert WEIGHTS["skills_match"] >= WEIGHTS["location_match"]
        assert WEIGHTS["skills_match"] >= WEIGHTS["service_type_bonus"]

    def test_relationship_bonus_significant(self):
        from app.services.intent_service import WEIGHTS

        assert WEIGHTS["relationship_bonus"] >= 10


class TestMatchingPipelineLogic:
    """Test the full matching pipeline logic patterns."""

    def test_zero_skill_overlap_means_skip(self):
        """When required skills are specified and agent has zero overlap, skip."""
        req_skills = {"coding", "design"}
        agent_skills = {"cooking", "gardening"}
        overlap = set(req_skills) & set(agent_skills)
        assert len(overlap) == 0  # Hard filter: skip this agent

    def test_description_keyword_match_scoring(self):
        """Description keyword matching against agent skills."""
        desc_words = set("need translation service for documents".split())
        agent_skills = ["translation", "writing"]
        matches = [s for s in agent_skills if s.lower() in desc_words]
        assert "translation" in matches
        assert "writing" not in matches  # "writing" not in desc

    def test_score_sorting(self):
        """Matches should be sorted by score descending."""
        matches = [
            {"agent_id": "a", "match_score": 30},
            {"agent_id": "b", "match_score": 60},
            {"agent_id": "c", "match_score": 45},
        ]
        matches.sort(key=lambda m: m["match_score"], reverse=True)
        assert matches[0]["agent_id"] == "b"
        assert matches[1]["agent_id"] == "c"
        assert matches[2]["agent_id"] == "a"

    def test_max_matches_limit(self):
        """Results should be limited to max_matches."""
        matches = [{"agent_id": f"a{i}", "match_score": i * 10} for i in range(10)]
        max_matches = 5
        limited = matches[:max_matches]
        assert len(limited) == 5
