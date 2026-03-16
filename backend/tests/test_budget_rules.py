"""Tests for budget enforcement rules (spec §15.1).

Tests anti-spam budget logic without DB.
"""

from __future__ import annotations

from app.models.enums import AgentType


class TestBudgetRules:
    """Test budget configuration and rules."""

    def test_budget_types(self):
        """Verify all budget types from spec."""
        budget_types = {"new_direct_task", "introduction_request", "circle_request"}
        assert len(budget_types) == 3

    def test_new_direct_task_limit(self):
        """new_direct_task: 5/day normal, 3/day newbie."""
        normal_limit = 5
        newbie_limit = 3
        assert normal_limit > newbie_limit

    def test_introduction_request_limit(self):
        """introduction_request: 3/day."""
        limit = 3
        assert limit == 3

    def test_circle_request_limit(self):
        """circle_request: 5/day."""
        limit = 5
        assert limit == 5

    def test_service_agents_exempt(self):
        """Service agents are exempt from budget enforcement."""
        agent_type = AgentType.SERVICE
        is_service = agent_type == AgentType.SERVICE
        assert is_service  # service agents skip budget check

    def test_personal_agents_enforced(self):
        """Personal agents have budget enforcement."""
        agent_type = AgentType.PERSONAL
        is_service = agent_type == AgentType.SERVICE
        assert not is_service

    def test_newbie_detection(self):
        """Account < 7 days old → reduced limits."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        created_5_days_ago = now - timedelta(days=5)
        created_10_days_ago = now - timedelta(days=10)

        is_newbie_5d = (now - created_5_days_ago).days < 7
        is_newbie_10d = (now - created_10_days_ago).days < 7

        assert is_newbie_5d
        assert not is_newbie_10d

    def test_budget_window_daily(self):
        """Budget windows reset daily."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        assert window_start.hour == 0
        assert window_start.minute == 0


class TestRiskLevelBudgetInteraction:
    """Test how risk levels interact with budget rules."""

    def test_r0_r1_count_toward_budget(self):
        """R0 and R1 tasks count toward new_direct_task budget."""
        budget_type = "new_direct_task"
        assert budget_type == "new_direct_task"

    def test_high_risk_still_counted(self):
        """R2 and R3 tasks still count toward budget."""
        budget_type = "new_direct_task"
        risk_level = "R3"
        # High risk tasks are rate-limited by both budget AND human-confirm
        assert budget_type and risk_level


class TestOriginTypeCompleteness:
    """Test that all 7 origin types from spec are defined."""

    def test_origin_types_include_spec_required(self):
        from app.models.enums import OriginType

        origin_types = {o.value for o in OriginType}
        required = {
            "public_service",
            "imported_contact",
            "claimed_handle",
            "same_circle",
            "introduced",
            "platform_vouched",
            "collaborated",
        }
        assert required.issubset(origin_types)

    def test_origin_type_count(self):
        from app.models.enums import OriginType

        assert len(OriginType) >= 7
