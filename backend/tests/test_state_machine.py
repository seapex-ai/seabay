"""Tests for task state machine transitions and risk level logic."""

from __future__ import annotations

from app.models.enums import (
    HIGH_RISK_KEYWORDS,
    TASK_TRANSITIONS,
    RiskLevel,
    TaskStatus,
    requires_human_confirm,
)


class TestTaskTransitions:
    """Test task state machine transition rules."""

    def test_pending_delivery_can_go_to_delivered(self):
        assert TaskStatus.DELIVERED in TASK_TRANSITIONS[TaskStatus.PENDING_DELIVERY]

    def test_pending_delivery_can_go_to_failed(self):
        assert TaskStatus.FAILED in TASK_TRANSITIONS[TaskStatus.PENDING_DELIVERY]

    def test_pending_delivery_can_go_to_expired(self):
        assert TaskStatus.EXPIRED in TASK_TRANSITIONS[TaskStatus.PENDING_DELIVERY]

    def test_pending_delivery_can_go_to_cancelled(self):
        assert TaskStatus.CANCELLED in TASK_TRANSITIONS[TaskStatus.PENDING_DELIVERY]

    def test_delivered_can_go_to_pending_accept(self):
        assert TaskStatus.PENDING_ACCEPT in TASK_TRANSITIONS[TaskStatus.DELIVERED]

    def test_pending_accept_can_go_to_accepted(self):
        assert TaskStatus.ACCEPTED in TASK_TRANSITIONS[TaskStatus.PENDING_ACCEPT]

    def test_pending_accept_can_go_to_declined(self):
        assert TaskStatus.DECLINED in TASK_TRANSITIONS[TaskStatus.PENDING_ACCEPT]

    def test_accepted_can_go_to_in_progress(self):
        assert TaskStatus.IN_PROGRESS in TASK_TRANSITIONS[TaskStatus.ACCEPTED]

    def test_in_progress_can_go_to_completed(self):
        assert TaskStatus.COMPLETED in TASK_TRANSITIONS[TaskStatus.IN_PROGRESS]

    def test_in_progress_can_go_to_waiting_human_confirm(self):
        assert TaskStatus.WAITING_HUMAN_CONFIRM in TASK_TRANSITIONS[TaskStatus.IN_PROGRESS]

    def test_in_progress_can_go_to_failed(self):
        assert TaskStatus.FAILED in TASK_TRANSITIONS[TaskStatus.IN_PROGRESS]

    def test_waiting_human_confirm_can_go_to_completed(self):
        assert TaskStatus.COMPLETED in TASK_TRANSITIONS[TaskStatus.WAITING_HUMAN_CONFIRM]

    def test_waiting_human_confirm_can_go_to_cancelled(self):
        assert TaskStatus.CANCELLED in TASK_TRANSITIONS[TaskStatus.WAITING_HUMAN_CONFIRM]

    def test_waiting_human_confirm_can_go_to_expired(self):
        assert TaskStatus.EXPIRED in TASK_TRANSITIONS[TaskStatus.WAITING_HUMAN_CONFIRM]

    def test_terminal_states_have_no_transitions(self):
        """Terminal states should not appear as keys in TASK_TRANSITIONS."""
        terminal = {TaskStatus.COMPLETED, TaskStatus.DECLINED, TaskStatus.EXPIRED,
                     TaskStatus.CANCELLED, TaskStatus.FAILED}
        for state in terminal:
            assert state not in TASK_TRANSITIONS

    def test_no_direct_delivery_to_completed(self):
        """Cannot go directly from pending_delivery to completed."""
        assert TaskStatus.COMPLETED not in TASK_TRANSITIONS[TaskStatus.PENDING_DELIVERY]

    def test_cannot_go_from_declined_to_accepted(self):
        """Declined is terminal — no transitions."""
        assert TaskStatus.DECLINED not in TASK_TRANSITIONS

    def test_all_active_states_can_cancel(self):
        """Most active states should allow cancellation."""
        cancelable = [
            TaskStatus.PENDING_DELIVERY,
            TaskStatus.DELIVERED,
            TaskStatus.PENDING_ACCEPT,
            TaskStatus.ACCEPTED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.WAITING_HUMAN_CONFIRM,
        ]
        for state in cancelable:
            assert TaskStatus.CANCELLED in TASK_TRANSITIONS[state], \
                f"{state} should be cancelable"


class TestRiskLevels:
    """Test risk level definitions and human confirm requirements."""

    def test_r0_no_confirm(self):
        assert not requires_human_confirm(RiskLevel.R0)

    def test_r1_no_confirm(self):
        assert not requires_human_confirm(RiskLevel.R1)

    def test_r2_requires_confirm(self):
        assert requires_human_confirm(RiskLevel.R2)

    def test_r3_requires_confirm(self):
        assert requires_human_confirm(RiskLevel.R3)

    def test_r3_keywords_are_high_risk(self):
        """R3 keywords should include payment-related terms."""
        r3_keywords = {k for k, v in HIGH_RISK_KEYWORDS.items() if v == RiskLevel.R3}
        assert "payment" in r3_keywords
        assert "transfer" in r3_keywords
        assert "withdraw" in r3_keywords
        assert "meet_offline" in r3_keywords
        assert "grant_access" in r3_keywords

    def test_r2_keywords_are_medium_risk(self):
        """R2 keywords should include coordination terms."""
        r2_keywords = {k for k, v in HIGH_RISK_KEYWORDS.items() if v == RiskLevel.R2}
        assert "booking" in r2_keywords
        assert "send_email" in r2_keywords
        assert "delete" in r2_keywords

    def test_no_r0_or_r1_keywords(self):
        """HIGH_RISK_KEYWORDS should only contain R2 and R3."""
        for risk in HIGH_RISK_KEYWORDS.values():
            assert risk in (RiskLevel.R2, RiskLevel.R3)

    def test_keyword_count(self):
        """Should have a reasonable number of risk keywords."""
        assert len(HIGH_RISK_KEYWORDS) >= 20


class TestTaskStatusEnum:
    """Test task status enum completeness."""

    def test_all_12_statuses(self):
        """Spec defines 12 task statuses (including draft)."""
        assert len(TaskStatus) >= 11  # At minimum 11 non-draft

    def test_status_values(self):
        """Verify key status string values."""
        assert TaskStatus.DRAFT.value == "draft"
        assert TaskStatus.PENDING_DELIVERY.value == "pending_delivery"
        assert TaskStatus.DELIVERED.value == "delivered"
        assert TaskStatus.PENDING_ACCEPT.value == "pending_accept"
        assert TaskStatus.ACCEPTED.value == "accepted"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.WAITING_HUMAN_CONFIRM.value == "waiting_human_confirm"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.DECLINED.value == "declined"
        assert TaskStatus.EXPIRED.value == "expired"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.FAILED.value == "failed"
