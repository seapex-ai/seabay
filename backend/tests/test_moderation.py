"""Tests for moderation service — auto-moderation rules and audit logging."""

from __future__ import annotations

from app.services.moderation_service import (
    AUTO_SUSPEND_IMPERSONATION,
    AUTO_SUSPEND_REPORT_COUNT,
    OBSERVATION_THRESHOLD,
    PRIORITY_REVIEW_VERIFICATION,
    clear_audit_log,
    get_audit_log,
    get_moderation_summary,
    log_admin_action,
)


class TestModerationConfig:
    """Test moderation configuration values."""

    def test_auto_suspend_threshold(self):
        """3+ unique reporters in 24h triggers auto-suspend."""
        assert AUTO_SUSPEND_REPORT_COUNT == 3

    def test_impersonation_threshold(self):
        """2+ impersonation reports triggers auto-suspend."""
        assert AUTO_SUSPEND_IMPERSONATION == 2

    def test_priority_review_verification(self):
        """github-verified reporters trigger priority review."""
        assert PRIORITY_REVIEW_VERIFICATION == "github"

    def test_observation_threshold(self):
        """1+ reports put agent under observation."""
        assert OBSERVATION_THRESHOLD == 1


class TestAuditLog:
    """Test moderation audit logging."""

    def setup_method(self):
        clear_audit_log()

    def test_log_admin_action(self):
        log_admin_action(
            "suspend", "agt_123", "agt_admin", "Suspended for abuse",
        )
        entries = get_audit_log()
        assert len(entries) == 1
        assert entries[0]["action"] == "suspend"
        assert entries[0]["agent_id"] == "agt_123"
        assert entries[0]["admin_id"] == "agt_admin"

    def test_log_multiple_actions(self):
        log_admin_action("suspend", "agt_1", "admin", "reason1")
        log_admin_action("unsuspend", "agt_1", "admin", "reason2")
        entries = get_audit_log()
        assert len(entries) == 2

    def test_filter_by_agent(self):
        log_admin_action("suspend", "agt_1", "admin", "r1")
        log_admin_action("suspend", "agt_2", "admin", "r2")
        entries = get_audit_log(agent_id="agt_1")
        assert len(entries) == 1
        assert entries[0]["agent_id"] == "agt_1"

    def test_limit(self):
        for i in range(100):
            log_admin_action("action", f"agt_{i}", "admin", "test")
        entries = get_audit_log(limit=10)
        assert len(entries) == 10

    def test_entries_have_timestamp(self):
        log_admin_action("suspend", "agt_1", "admin", "test")
        entries = get_audit_log()
        assert "timestamp" in entries[0]

    def test_clear_log(self):
        log_admin_action("suspend", "agt_1", "admin", "test")
        clear_audit_log()
        assert len(get_audit_log()) == 0


class TestModerationSummary:
    """Test moderation summary statistics."""

    def setup_method(self):
        clear_audit_log()

    def test_empty_summary(self):
        summary = get_moderation_summary()
        assert summary["total_actions"] == 0
        assert summary["by_action"] == {}

    def test_summary_with_actions(self):
        log_admin_action("suspend", "agt_1", "admin", "r1")
        log_admin_action("suspend", "agt_2", "admin", "r2")
        log_admin_action("unsuspend", "agt_1", "admin", "r3")
        summary = get_moderation_summary()
        assert summary["total_actions"] == 3
        assert summary["by_action"]["suspend"] == 2
        assert summary["by_action"]["unsuspend"] == 1
