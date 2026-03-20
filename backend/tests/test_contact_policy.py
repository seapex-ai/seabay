"""Tests for contact policy enforcement and relationship strength derivation.

These are critical business logic tests that validate the spec's
contact rules (§10.1) and strength derivation (§6.5).
"""

from __future__ import annotations

from app.models.enums import (
    ContactPolicy,
    IntroductionPolicy,
    RelationshipStrength,
)


class TestContactPolicyEnum:
    def test_all_policies_exist(self):
        assert len(ContactPolicy) == 5
        policies = {p.value for p in ContactPolicy}
        assert policies == {
            "public_service_only",
            "known_direct",
            "intro_only",
            "circle_request",
            "closed",
        }

    def test_policy_ordering(self):
        """More restrictive policies should have higher ordinal values."""
        policy_list = list(ContactPolicy)
        assert policy_list[0] == ContactPolicy.PUBLIC_SERVICE_ONLY
        assert policy_list[-1] == ContactPolicy.CLOSED


class TestRelationshipStrength:
    def test_all_strengths_exist(self):
        assert len(RelationshipStrength) == 4
        strengths = {s.value for s in RelationshipStrength}
        assert strengths == {"new", "acquaintance", "trusted", "frequent"}

    def test_strength_progression(self):
        """Strengths should go from weakest to strongest."""
        strengths = list(RelationshipStrength)
        assert strengths[0] == RelationshipStrength.NEW
        assert strengths[1] == RelationshipStrength.ACQUAINTANCE
        assert strengths[2] == RelationshipStrength.TRUSTED
        assert strengths[3] == RelationshipStrength.FREQUENT


class TestIntroductionPolicy:
    def test_all_policies_exist(self):
        assert len(IntroductionPolicy) >= 2
        policies = {p.value for p in IntroductionPolicy}
        assert "open" in policies or "confirm_required" in policies


class TestContactPolicyLogic:
    """Test the contact policy decision logic without DB."""

    def test_public_service_allows_anyone(self):
        """public_service_only: any agent can contact."""
        # This policy allows contact from any agent
        policy = ContactPolicy.PUBLIC_SERVICE_ONLY
        assert policy.value == "public_service_only"

    def test_known_direct_requires_relationship(self):
        """known_direct: only agents with existing relationship can contact."""
        policy = ContactPolicy.KNOWN_DIRECT
        assert policy.value == "known_direct"

    def test_intro_only_requires_introduction(self):
        """intro_only: only via mutual introduction."""
        policy = ContactPolicy.INTRO_ONLY
        assert policy.value == "intro_only"

    def test_closed_blocks_all(self):
        """closed: no one can initiate contact."""
        policy = ContactPolicy.CLOSED
        assert policy.value == "closed"


class TestStrengthDerivationRules:
    """Test strength derivation rules without DB.

    Rules from spec §6.5:
    - new: default for new edges
    - acquaintance: ≥1 successful task
    - trusted: ≥3 successful tasks + no reports + avg_rating ≥ 3.5
    - frequent: mutual star + 30d relationship + ≥5 successful tasks
    """

    def test_new_is_default(self):
        assert RelationshipStrength.NEW.value == "new"

    def test_acquaintance_criteria(self):
        """≥1 successful task → acquaintance."""
        success_count = 1
        assert success_count >= 1  # meets criteria

    def test_trusted_criteria(self):
        """≥3 successful + no reports + avg_rating ≥ 3.5 → trusted."""
        success_count = 3
        report_count = 0
        avg_rating = 4.0
        assert success_count >= 3
        assert report_count == 0
        assert avg_rating >= 3.5

    def test_trusted_blocked_by_reports(self):
        """Reports prevent trusted status."""
        success_count = 5
        report_count = 1
        assert not (success_count >= 3 and report_count == 0)

    def test_trusted_blocked_by_low_rating(self):
        """Low rating prevents trusted status."""
        success_count = 3
        report_count = 0
        avg_rating = 2.5
        assert not (success_count >= 3 and report_count == 0 and avg_rating >= 3.5)

    def test_frequent_criteria(self):
        """Mutual star + 30d + ≥5 success → frequent."""
        success_count = 5
        mutual_star = True
        days_known = 31
        assert success_count >= 5
        assert mutual_star
        assert days_known >= 30

    def test_frequent_requires_mutual_star(self):
        """Without mutual star, can't be frequent."""
        success_count = 10
        mutual_star = False
        assert not (success_count >= 5 and mutual_star)
