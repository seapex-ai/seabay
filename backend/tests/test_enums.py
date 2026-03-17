"""Test enum definitions and task state machine."""

from app.models.enums import (
    HIGH_RISK_KEYWORDS,
    TASK_TRANSITIONS,
    RiskLevel,
    TaskStatus,
    requires_human_confirm,
)


def test_task_transitions_complete():
    """Verify all non-terminal states have defined transitions."""
    non_terminal = {
        TaskStatus.PENDING_DELIVERY,
        TaskStatus.DELIVERED,
        TaskStatus.PENDING_ACCEPT,
        TaskStatus.ACCEPTED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.WAITING_HUMAN_CONFIRM,
    }
    for status in non_terminal:
        assert status in TASK_TRANSITIONS, f"Missing transitions for {status}"
        assert len(TASK_TRANSITIONS[status]) > 0


def test_terminal_states_have_no_transitions():
    """Terminal states should not appear in transition dict."""
    terminal = {
        TaskStatus.COMPLETED,
        TaskStatus.DECLINED,
        TaskStatus.EXPIRED,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    }
    for status in terminal:
        assert status not in TASK_TRANSITIONS


def test_risk_levels():
    assert not requires_human_confirm(RiskLevel.R0)
    assert not requires_human_confirm(RiskLevel.R1)
    assert requires_human_confirm(RiskLevel.R2)
    assert requires_human_confirm(RiskLevel.R3)


def test_high_risk_keywords():
    assert HIGH_RISK_KEYWORDS["payment"] == RiskLevel.R3
    assert HIGH_RISK_KEYWORDS["booking"] == RiskLevel.R2
    assert len(HIGH_RISK_KEYWORDS) > 20


def test_pending_delivery_transitions():
    transitions = TASK_TRANSITIONS[TaskStatus.PENDING_DELIVERY]
    assert TaskStatus.DELIVERED in transitions
    assert TaskStatus.FAILED in transitions
    assert TaskStatus.EXPIRED in transitions
    assert TaskStatus.CANCELLED in transitions


def test_in_progress_can_go_to_human_confirm():
    transitions = TASK_TRANSITIONS[TaskStatus.IN_PROGRESS]
    assert TaskStatus.WAITING_HUMAN_CONFIRM in transitions
    assert TaskStatus.COMPLETED in transitions
