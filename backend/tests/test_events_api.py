"""Tests for event SSE endpoints — stream and status.

Covers SSE event stream format and connection status.
Uses the full ASGI client from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import notification_service


async def _register(client: AsyncClient, slug: str, agent_type: str = "service") -> dict:
    resp = await client.post("/v1/agents/register", json={
        "slug": slug,
        "display_name": f"Test {slug}",
        "agent_type": agent_type,
    })
    return resp.json()


class TestEventStream:
    """Test GET /v1/events/stream — SSE format."""

    @pytest.mark.asyncio
    async def test_event_stream_requires_auth(self, client: AsyncClient):
        resp = await client.get("/v1/events/stream")
        assert resp.status_code == 422  # missing auth header

    @pytest.mark.asyncio
    async def test_event_stream_returns_sse_content_type(self, client: AsyncClient):
        """The stream endpoint should return text/event-stream."""
        agent = await _register(client, "event-stream-1")
        # Note: AsyncClient doesn't truly support streaming well in tests.
        # We verify the response starts correctly via stream context manager.
        async with client.stream(
            "GET",
            "/v1/events/stream",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            # Read the initial connected event
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    assert "connected" in line
                    break
                if line.startswith("data:"):
                    break


class TestEventStatus:
    """Test GET /v1/events/status."""

    @pytest.mark.asyncio
    async def test_event_status(self, client: AsyncClient):
        agent = await _register(client, "event-status-1")
        resp = await client.get(
            "/v1/events/status",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == agent["id"]
        assert "active_connections" in data
        assert "is_connected" in data
        assert isinstance(data["active_connections"], int)
        assert isinstance(data["is_connected"], bool)

    @pytest.mark.asyncio
    async def test_event_status_no_connections(self, client: AsyncClient):
        """An agent with no SSE connection should show 0."""
        agent = await _register(client, "event-status-none")
        resp = await client.get(
            "/v1/events/status",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_connections"] == 0
        assert data["is_connected"] is False


class TestSSEFormatting:
    """Test SSE message formatting from notification_service."""

    def test_format_sse_basic(self):
        formatted = notification_service._format_sse("test_event", {"key": "value"})
        assert "event: test_event" in formatted
        assert "data:" in formatted
        assert '"key"' in formatted
        assert formatted.endswith("\n\n")

    def test_format_sse_with_event_id(self):
        formatted = notification_service._format_sse("test_event", {"key": "val"}, event_id="evt_123")
        assert "id: evt_123" in formatted
        assert "event: test_event" in formatted

    def test_format_sse_without_event_id(self):
        formatted = notification_service._format_sse("test_event", {"key": "val"})
        assert "id:" not in formatted


class TestNotificationServiceInMemory:
    """Test the in-memory notification service primitives."""

    def test_connection_count_empty(self):
        count = notification_service.get_connection_count("nonexistent_agent")
        assert count == 0

    def test_connected_agents_empty_initially(self):
        # May have agents from other tests, but should not error
        agents = notification_service.get_connected_agents()
        assert isinstance(agents, list)

    @pytest.mark.asyncio
    async def test_push_event_no_subscribers(self):
        """push_event with no subscribers returns 0."""
        delivered = await notification_service.push_event(
            "nonexistent_agent",
            "test.event",
            {"data": "test"},
        )
        assert delivered == 0
