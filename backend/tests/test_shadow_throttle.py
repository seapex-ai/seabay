"""Tests for shadow throttle service — anti-abuse delivery delay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.shadow_throttle_service import (
    NEW_ACCOUNT_DAYS,
    REPORT_THRESHOLD,
    SPIKE_THRESHOLD,
    THROTTLE_MAX_DELAY,
    THROTTLE_MIN_DELAY,
    check_should_throttle,
    clear_throttle,
    get_throttle_stats,
    is_throttled,
    record_first_contact,
    reset_all,
)


class TestThrottleConfig:
    """Test throttle configuration values."""

    def test_min_delay(self):
        assert THROTTLE_MIN_DELAY == 30

    def test_max_delay(self):
        assert THROTTLE_MAX_DELAY == 120

    def test_new_account_days(self):
        assert NEW_ACCOUNT_DAYS == 7

    def test_spike_threshold(self):
        assert SPIKE_THRESHOLD == 3

    def test_report_threshold(self):
        assert REPORT_THRESHOLD == 2


class TestThrottleDecision:
    """Test throttle trigger conditions."""

    def setup_method(self):
        reset_all()

    def test_no_throttle_normal_agent(self):
        """Normal agent should not be throttled."""
        old_agent = datetime.now(timezone.utc) - timedelta(days=30)
        result = check_should_throttle(
            "agt_normal", old_agent, report_count=0, daily_budget_used_pct=0.3,
        )
        assert result is None

    def test_throttle_new_account_high_usage(self):
        """New account with 80%+ budget usage should be throttled."""
        new_agent = datetime.now(timezone.utc) - timedelta(days=2)
        result = check_should_throttle(
            "agt_new_heavy", new_agent, report_count=0, daily_budget_used_pct=0.85,
        )
        assert result is not None
        assert THROTTLE_MIN_DELAY <= result <= THROTTLE_MAX_DELAY

    def test_no_throttle_new_account_low_usage(self):
        """New account with low usage should not be throttled."""
        new_agent = datetime.now(timezone.utc) - timedelta(days=2)
        result = check_should_throttle(
            "agt_new_light", new_agent, report_count=0, daily_budget_used_pct=0.3,
        )
        assert result is None

    def test_throttle_reports_threshold(self):
        """Agent with 2+ reports should be throttled."""
        old_agent = datetime.now(timezone.utc) - timedelta(days=30)
        result = check_should_throttle(
            "agt_reported", old_agent, report_count=3, daily_budget_used_pct=0.1,
        )
        assert result is not None

    def test_no_throttle_one_report(self):
        """1 report is below threshold."""
        old_agent = datetime.now(timezone.utc) - timedelta(days=30)
        result = check_should_throttle(
            "agt_one_report", old_agent, report_count=1, daily_budget_used_pct=0.1,
        )
        assert result is None


class TestSpikeDetection:
    """Test first-contact spike detection."""

    def setup_method(self):
        reset_all()

    def test_no_spike_few_contacts(self):
        """Less than 3 first-contacts is not a spike."""
        record_first_contact("agt_slow")
        record_first_contact("agt_slow")
        old_agent = datetime.now(timezone.utc) - timedelta(days=30)
        result = check_should_throttle(
            "agt_slow", old_agent, report_count=0, daily_budget_used_pct=0.1,
        )
        assert result is None

    def test_spike_detected(self):
        """3+ first-contacts in 1 hour triggers spike."""
        for _ in range(4):
            record_first_contact("agt_spammer")
        old_agent = datetime.now(timezone.utc) - timedelta(days=30)
        result = check_should_throttle(
            "agt_spammer", old_agent, report_count=0, daily_budget_used_pct=0.1,
        )
        assert result is not None


class TestThrottleState:
    """Test throttle state management."""

    def setup_method(self):
        reset_all()

    def test_not_throttled_initially(self):
        assert is_throttled("agt_new") is False

    def test_throttled_after_trigger(self):
        new_agent = datetime.now(timezone.utc) - timedelta(days=1)
        check_should_throttle(
            "agt_triggered", new_agent, report_count=3, daily_budget_used_pct=0.1,
        )
        assert is_throttled("agt_triggered") is True

    def test_clear_throttle(self):
        new_agent = datetime.now(timezone.utc) - timedelta(days=1)
        check_should_throttle(
            "agt_cleared", new_agent, report_count=3, daily_budget_used_pct=0.1,
        )
        clear_throttle("agt_cleared")
        assert is_throttled("agt_cleared") is False

    def test_stats_empty_initially(self):
        stats = get_throttle_stats()
        assert stats["total_throttled"] == 0
        assert stats["tracker_agents"] == 0
