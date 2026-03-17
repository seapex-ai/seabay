"""Tests for webhook configuration service."""

from __future__ import annotations

from app.services.webhook_config_service import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAYS,
    DEFAULT_TIMEOUT,
    WEBHOOK_EVENT_TYPES,
    get_webhook_config,
    list_event_types,
    should_deliver,
)


class TestWebhookEventTypes:
    """Test webhook event type definitions."""

    def test_task_created(self):
        assert "task.created" in WEBHOOK_EVENT_TYPES

    def test_task_accepted(self):
        assert "task.accepted" in WEBHOOK_EVENT_TYPES

    def test_task_declined(self):
        assert "task.declined" in WEBHOOK_EVENT_TYPES

    def test_task_completed(self):
        assert "task.completed" in WEBHOOK_EVENT_TYPES

    def test_task_cancelled(self):
        assert "task.cancelled" in WEBHOOK_EVENT_TYPES

    def test_task_failed(self):
        assert "task.failed" in WEBHOOK_EVENT_TYPES

    def test_task_expired(self):
        assert "task.expired" in WEBHOOK_EVENT_TYPES

    def test_task_human_confirm(self):
        assert "task.human_confirm_required" in WEBHOOK_EVENT_TYPES

    def test_introduction_received(self):
        assert "introduction.received" in WEBHOOK_EVENT_TYPES

    def test_introduction_accepted(self):
        assert "introduction.accepted" in WEBHOOK_EVENT_TYPES

    def test_introduction_declined(self):
        assert "introduction.declined" in WEBHOOK_EVENT_TYPES

    def test_introduction_expired(self):
        assert "introduction.expired" in WEBHOOK_EVENT_TYPES

    def test_circle_join_request(self):
        assert "circle.join_request" in WEBHOOK_EVENT_TYPES

    def test_circle_member_joined(self):
        assert "circle.member_joined" in WEBHOOK_EVENT_TYPES

    def test_circle_member_left(self):
        assert "circle.member_left" in WEBHOOK_EVENT_TYPES

    def test_report_received(self):
        assert "report.received" in WEBHOOK_EVENT_TYPES

    def test_at_least_fifteen_events(self):
        assert len(WEBHOOK_EVENT_TYPES) >= 15

    def test_all_events_have_dot_separator(self):
        for event in WEBHOOK_EVENT_TYPES:
            assert "." in event, f"Event '{event}' missing dot separator"


class TestWebhookDefaults:
    """Test webhook default configuration values."""

    def test_default_timeout(self):
        assert DEFAULT_TIMEOUT == 10.0

    def test_default_max_retries(self):
        assert DEFAULT_MAX_RETRIES == 3

    def test_retry_delays(self):
        assert DEFAULT_RETRY_DELAYS == [0, 1, 5, 25]

    def test_retry_delays_exponential(self):
        """Verify delays follow exponential pattern."""
        for i in range(1, len(DEFAULT_RETRY_DELAYS)):
            assert DEFAULT_RETRY_DELAYS[i] > DEFAULT_RETRY_DELAYS[i - 1]


class TestWebhookConfigFunctions:
    """Test in-memory webhook config management."""

    def test_get_config_nonexistent(self):
        assert get_webhook_config("nonexistent_agent_xxx") is None

    def test_should_deliver_no_config(self):
        """No config = deliver everything."""
        assert should_deliver("nonexistent_agent_xxx", "task.created") is True

    def test_list_event_types_sorted(self):
        events = list_event_types()
        assert events == sorted(events)

    def test_list_event_types_matches_set(self):
        events = list_event_types()
        assert set(events) == WEBHOOK_EVENT_TYPES
