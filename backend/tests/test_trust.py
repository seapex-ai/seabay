"""Tests for trust_service — signal computation and scoring."""

from __future__ import annotations

from app.services.trust_service import compute_trust_score


class TestTrustScoreComputation:
    """Test trust score formula (no DB required)."""

    def test_empty_signals(self):
        """Empty signals should return 0."""
        assert compute_trust_score({}) == 0.0

    def test_perfect_signals(self):
        """Perfect signals should score high."""
        signals = {
            "verification_weight": 4,  # manual_review (max)
            "success_rate_7d": 1.0,
            "report_rate_30d": 0.0,
            "human_confirm_success_rate": 1.0,
            "cancel_expire_rate_30d": 0.0,
        }
        score = compute_trust_score(signals)
        # 25 + 25 + 0 + 15 + 0 = 65... wait:
        # ver_norm = 4/4 = 1.0 → 25
        # success = 1.0 → 25
        # report = 0.0 → -0
        # confirm = 1.0 → 15
        # cancel = 0.0 → -0
        # Total = 65
        assert score == 65.0

    def test_no_verification_perfect_otherwise(self):
        """No verification but perfect behavior."""
        signals = {
            "verification_weight": 0,
            "success_rate_7d": 1.0,
            "report_rate_30d": 0.0,
            "human_confirm_success_rate": 1.0,
            "cancel_expire_rate_30d": 0.0,
        }
        score = compute_trust_score(signals)
        # 0 + 25 + 0 + 15 + 0 = 40
        assert score == 40.0

    def test_high_report_rate_decreases_score(self):
        """High report rate should significantly decrease score."""
        good = {
            "verification_weight": 2,
            "success_rate_7d": 0.8,
            "report_rate_30d": 0.0,
            "human_confirm_success_rate": 1.0,
            "cancel_expire_rate_30d": 0.0,
        }
        bad = {**good, "report_rate_30d": 0.5}

        good_score = compute_trust_score(good)
        bad_score = compute_trust_score(bad)
        assert good_score > bad_score
        assert good_score - bad_score == 10.0  # 0.5 * 20

    def test_high_cancel_rate_decreases_score(self):
        """High cancel/expire rate should decrease score."""
        normal = {
            "verification_weight": 2,
            "success_rate_7d": 0.9,
            "report_rate_30d": 0.0,
            "human_confirm_success_rate": 1.0,
            "cancel_expire_rate_30d": 0.0,
        }
        high_cancel = {**normal, "cancel_expire_rate_30d": 0.3}

        assert compute_trust_score(normal) > compute_trust_score(high_cancel)

    def test_score_clamped_to_0_100(self):
        """Score should never go below 0 or above 100."""
        terrible = {
            "verification_weight": 0,
            "success_rate_7d": 0.0,
            "report_rate_30d": 5.0,
            "human_confirm_success_rate": 0.0,
            "cancel_expire_rate_30d": 5.0,
        }
        assert compute_trust_score(terrible) == 0.0

    def test_email_verification_adds_points(self):
        """Email verification (weight=1) should add some points."""
        no_ver = {"verification_weight": 0, "success_rate_7d": 0.5}
        email_ver = {"verification_weight": 1, "success_rate_7d": 0.5}

        diff = compute_trust_score(email_ver) - compute_trust_score(no_ver)
        assert diff > 0
        # 1/4 * 25 = 6.25
        assert abs(diff - 6.25) < 0.01

    def test_missing_keys_use_defaults(self):
        """Missing signal keys should use safe defaults."""
        partial = {"verification_weight": 2}
        score = compute_trust_score(partial)
        # ver_norm = 0.5 → 12.5
        # success = 1.0 (default) → 25
        # report = 0.0 (default) → 0
        # confirm = 1.0 (default) → 15
        # cancel = 0.0 (default) → 0
        assert score == 52.5


class TestTrustVsPopularitySeparation:
    """Verify trust and popularity are kept separate (spec §14)."""

    def test_popularity_not_in_trust_score(self):
        """Popularity signals should NOT affect trust score."""
        signals = {
            "verification_weight": 2,
            "success_rate_7d": 0.8,
            "report_rate_30d": 0.0,
            "human_confirm_success_rate": 1.0,
            "cancel_expire_rate_30d": 0.0,
            # These should be ignored by trust:
            "task_received_count": 10000,
            "profile_views_7d": 50000,
            "search_appearances_7d": 100000,
        }
        without_pop = {k: v for k, v in signals.items()
                       if k not in ("task_received_count", "profile_views_7d", "search_appearances_7d")}

        assert compute_trust_score(signals) == compute_trust_score(without_pop)
