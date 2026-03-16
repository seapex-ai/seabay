"""Tests for new account restrictions service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.new_account_service import (
    ESTABLISHED_LIMITS,
    NEW_ACCOUNT_DAYS,
    NEW_ACCOUNT_LIMITS,
    check_new_account_restriction,
    get_account_status,
    get_daily_limit,
    is_new_account,
)


class FakeAgent:
    def __init__(self, days_old: int):
        self.created_at = datetime.now(timezone.utc) - timedelta(days=days_old)


class TestNewAccountDetection:
    """Test new account age detection."""

    def test_one_day_old_is_new(self):
        agent = FakeAgent(1)
        assert is_new_account(agent) is True

    def test_six_days_old_is_new(self):
        agent = FakeAgent(6)
        assert is_new_account(agent) is True

    def test_seven_days_old_not_new(self):
        agent = FakeAgent(7)
        assert is_new_account(agent) is False

    def test_thirty_days_old_not_new(self):
        agent = FakeAgent(30)
        assert is_new_account(agent) is False


class TestDailyLimits:
    """Test daily limit calculations."""

    def test_new_account_task_limit(self):
        agent = FakeAgent(1)
        assert get_daily_limit(agent, "new_direct_task") == 10

    def test_established_task_limit(self):
        agent = FakeAgent(30)
        assert get_daily_limit(agent, "new_direct_task") == 20

    def test_new_account_first_contact(self):
        agent = FakeAgent(1)
        assert get_daily_limit(agent, "first_contact") == 2

    def test_established_first_contact(self):
        agent = FakeAgent(30)
        assert get_daily_limit(agent, "first_contact") == 5

    def test_new_account_reduced_introductions(self):
        agent = FakeAgent(1)
        assert get_daily_limit(agent, "introduction_request") == 2  # spec: 2/day for new

    def test_established_introductions(self):
        agent = FakeAgent(30)
        assert get_daily_limit(agent, "introduction_request") == 3

    def test_new_account_no_circle_create(self):
        agent = FakeAgent(1)
        assert get_daily_limit(agent, "circle_create") == 0


class TestRestrictions:
    """Test new account action restrictions."""

    def test_new_cannot_create_circle(self):
        agent = FakeAgent(1)
        with pytest.raises(Exception, match="New accounts cannot create circles"):
            check_new_account_restriction(agent, "circle_create")

    def test_new_can_introduce_with_limit(self):
        """New accounts CAN introduce (with reduced 2/day limit via budget)."""
        agent = FakeAgent(1)
        check_new_account_restriction(agent, "introduction_request")  # no exception

    def test_established_can_create_circle(self):
        agent = FakeAgent(30)
        check_new_account_restriction(agent, "circle_create")  # no exception

    def test_established_can_introduce(self):
        agent = FakeAgent(30)
        check_new_account_restriction(agent, "introduction_request")  # no exception

    def test_new_can_task(self):
        """New accounts CAN create tasks (just with lower limits)."""
        agent = FakeAgent(1)
        check_new_account_restriction(agent, "new_direct_task")  # no exception


class TestAccountStatus:
    """Test account status reporting."""

    def test_new_account_status(self):
        agent = FakeAgent(2)
        status = get_account_status(agent)
        assert status["is_new_account"] is True
        assert status["account_age_days"] == 2
        assert status["days_until_established"] == 5
        assert status["restrictions"]["can_create_circles"] is False
        assert status["restrictions"]["can_initiate_introductions"] is True  # allowed with reduced limit

    def test_established_account_status(self):
        agent = FakeAgent(30)
        status = get_account_status(agent)
        assert status["is_new_account"] is False
        assert status["days_until_established"] == 0
        assert status["restrictions"]["can_create_circles"] is True
        assert status["restrictions"]["can_initiate_introductions"] is True

    def test_status_limits(self):
        new_agent = FakeAgent(1)
        old_agent = FakeAgent(30)
        new_status = get_account_status(new_agent)
        old_status = get_account_status(old_agent)

        assert new_status["daily_limits"]["new_direct_task"] < old_status["daily_limits"]["new_direct_task"]


class TestConfig:
    """Test configuration values match spec."""

    def test_new_account_window(self):
        assert NEW_ACCOUNT_DAYS == 7

    def test_new_limits_subset(self):
        """New account limits should cover all established limit types."""
        assert set(NEW_ACCOUNT_LIMITS.keys()) == set(ESTABLISHED_LIMITS.keys())

    def test_new_limits_lower_or_equal(self):
        """New account limits should be <= established limits."""
        for key in NEW_ACCOUNT_LIMITS:
            assert NEW_ACCOUNT_LIMITS[key] <= ESTABLISHED_LIMITS[key]
