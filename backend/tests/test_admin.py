"""Tests for admin route helpers and configuration."""

from __future__ import annotations


class TestAdminAccess:
    """Test admin access control logic."""

    def test_admin_requires_manual_review(self):
        """Admin access requires manual_review verification level."""
        from unittest.mock import MagicMock

        from app.api.v1.admin import _require_admin
        from app.core.exceptions import ForbiddenError

        agent = MagicMock()
        agent.verification_level = "none"
        try:
            _require_admin(agent)
            assert False, "Should have raised"
        except ForbiddenError:
            pass

    def test_admin_passes_for_manual_review(self):
        """manual_review level should pass admin check."""
        from unittest.mock import MagicMock

        from app.api.v1.admin import _require_admin

        agent = MagicMock()
        agent.verification_level = "manual_review"
        _require_admin(agent)  # no exception

    def test_admin_rejects_email_verified(self):
        """Email-verified agents should not have admin access."""
        from unittest.mock import MagicMock

        from app.api.v1.admin import _require_admin
        from app.core.exceptions import ForbiddenError

        agent = MagicMock()
        agent.verification_level = "email"
        try:
            _require_admin(agent)
            assert False, "Should have raised"
        except ForbiddenError:
            pass

    def test_admin_rejects_github_verified(self):
        """GitHub-verified agents should not have admin access."""
        from unittest.mock import MagicMock

        from app.api.v1.admin import _require_admin
        from app.core.exceptions import ForbiddenError

        agent = MagicMock()
        agent.verification_level = "github"
        try:
            _require_admin(agent)
            assert False, "Should have raised"
        except ForbiddenError:
            pass


class TestReportFormatting:
    """Test report response formatting."""

    def test_report_to_dict(self):
        """_report_to_dict should include all fields."""
        from unittest.mock import MagicMock

        from app.api.v1.admin import _report_to_dict

        report = MagicMock()
        report.id = "rpt_123"
        report.reporter_agent_id = "agt_1"
        report.reported_agent_id = "agt_2"
        report.task_id = "tsk_456"
        report.reason_code = "spam"
        report.notes = "Test notes"
        report.reporter_verification_level = "email"
        report.status = "pending"
        report.reviewed_by = None
        report.reviewed_at = None
        report.created_at = "2026-03-13T00:00:00Z"

        result = _report_to_dict(report)
        assert result["id"] == "rpt_123"
        assert result["reason_code"] == "spam"
        assert result["status"] == "pending"

    def test_agent_admin_dict(self):
        """_agent_admin_dict should include admin-relevant fields."""
        from unittest.mock import MagicMock

        from app.api.v1.admin import _agent_admin_dict

        agent = MagicMock()
        agent.id = "agt_123"
        agent.slug = "test-agent"
        agent.display_name = "Test Agent"
        agent.agent_type = "service"
        agent.status = "online"
        agent.verification_level = "github"
        agent.contact_policy = "known_direct"
        agent.visibility_scope = "public"
        agent.last_seen_at = None
        agent.suspended_at = None
        agent.created_at = "2026-03-13T00:00:00Z"

        result = _agent_admin_dict(agent)
        assert result["id"] == "agt_123"
        assert result["status"] == "online"
        assert result["verification_level"] == "github"


class TestReportReasonCodes:
    """Test report reason code completeness."""

    def test_all_reason_codes_exist(self):
        """All spec-required reason codes should be defined."""
        from app.models.enums import ReportReasonCode

        codes = {c.value for c in ReportReasonCode}
        required = {"spam", "impersonation", "unsafe_request", "policy_violation", "harassment", "other"}
        assert required.issubset(codes)

    def test_reason_code_count(self):
        """Should have at least 6 reason codes."""
        from app.models.enums import ReportReasonCode

        assert len(ReportReasonCode) >= 6


class TestReportStatus:
    """Test report status completeness."""

    def test_all_statuses_exist(self):
        """All report statuses should be defined."""
        from app.models.enums import ReportStatus

        statuses = {s.value for s in ReportStatus}
        required = {"pending", "reviewed", "actioned", "dismissed"}
        assert required.issubset(statuses)
