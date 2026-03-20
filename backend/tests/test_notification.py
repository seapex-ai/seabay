"""Tests for notification service — SSE event bus (in-memory fallback)."""

from __future__ import annotations

import asyncio

import pytest

from app.services import notification_service
from app.services.notification_service import (
    _format_sse,
    get_connected_agents,
    get_connection_count,
    push_event,
    subscribe,
)


@pytest.fixture(autouse=True)
def _force_in_memory():
    """Force in-memory mode for all notification tests (no Redis needed)."""
    notification_service._reset_for_testing()
    notification_service._redis_available = False
    yield
    notification_service._reset_for_testing()


class TestSSEFormatting:
    def test_format_basic(self):
        result = _format_sse("test", {"key": "value"})
        assert "event: test" in result
        assert '"key": "value"' in result
        assert result.endswith("\n\n")

    def test_format_with_event_id(self):
        result = _format_sse("test", {"k": "v"}, event_id="evt_123")
        assert "id: evt_123" in result
        assert "event: test" in result

    def test_format_no_event_id(self):
        result = _format_sse("test", {"k": "v"})
        assert "id:" not in result


class TestSubscription:
    @pytest.mark.asyncio
    async def test_subscribe_yields_connected_event(self):
        gen = subscribe("agent_test_1")
        first = await gen.__anext__()
        assert "event: connected" in first
        assert "agent_test_1" in first
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_connection_count(self):
        gen = subscribe("agent_test_2")
        await gen.__anext__()  # consume connected event
        assert get_connection_count("agent_test_2") == 1
        await gen.aclose()
        # After close, give a tick for cleanup
        await asyncio.sleep(0.01)
        assert get_connection_count("agent_test_2") == 0

    @pytest.mark.asyncio
    async def test_connected_agents(self):
        gen = subscribe("agent_test_3")
        await gen.__anext__()
        assert "agent_test_3" in get_connected_agents()
        await gen.aclose()
        await asyncio.sleep(0.01)
        assert "agent_test_3" not in get_connected_agents()


class TestPushEvent:
    @pytest.mark.asyncio
    async def test_push_no_subscribers(self):
        count = await push_event("no_one", "test", {"k": "v"})
        assert count == 0

    @pytest.mark.asyncio
    async def test_push_to_subscriber(self):
        gen = subscribe("agent_push_1")
        await gen.__anext__()  # connected

        await push_event("agent_push_1", "task.created", {"task_id": "tsk_1"})
        event = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
        assert "event: task.created" in event
        assert "tsk_1" in event
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_push_to_multiple_connections(self):
        gen1 = subscribe("agent_push_2")
        gen2 = subscribe("agent_push_2")
        await gen1.__anext__()
        await gen2.__anext__()

        count = await push_event("agent_push_2", "test", {"k": "v"})
        assert count == 2

        await gen1.aclose()
        await gen2.aclose()
