"""Tests for public API routes — stats, directory, agent card.

Covers public-facing endpoints that require no authentication.
Uses the full ASGI client from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, slug: str, agent_type: str = "service") -> dict:
    resp = await client.post("/v1/agents/register", json={
        "slug": slug,
        "display_name": f"Test {slug}",
        "agent_type": agent_type,
    })
    return resp.json()


async def _make_public_service_agent(client: AsyncClient, slug: str) -> dict:
    """Register a service agent and set visibility to public."""
    agent = await _register(client, slug, "service")
    await client.patch(
        f"/v1/agents/{agent['id']}",
        json={"visibility_scope": "public"},
        headers={"Authorization": f"Bearer {agent['api_key']}"},
    )
    return agent


class TestPublicStats:
    """Test GET /v1/public/stats."""

    @pytest.mark.asyncio
    async def test_public_stats(self, client: AsyncClient):
        resp = await client.get("/v1/public/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks_completed" in data
        assert "service_agents_available" in data
        assert "total_agents" in data
        assert isinstance(data["tasks_completed"], int)
        assert isinstance(data["service_agents_available"], int)
        assert isinstance(data["total_agents"], int)

    @pytest.mark.asyncio
    async def test_public_stats_no_auth_required(self, client: AsyncClient):
        """Public stats should work without authentication."""
        resp = await client.get("/v1/public/stats")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stats_counts_increase_after_registration(self, client: AsyncClient):
        # Get initial stats
        resp1 = await client.get("/v1/public/stats")
        initial_total = resp1.json()["total_agents"]

        # Register a new agent
        await _register(client, "public-stats-new-agent")

        # Check updated stats
        resp2 = await client.get("/v1/public/stats")
        new_total = resp2.json()["total_agents"]
        assert new_total > initial_total


class TestPublicAgentDirectory:
    """Test GET /v1/public/agents."""

    @pytest.mark.asyncio
    async def test_list_public_agents(self, client: AsyncClient):
        resp = await client.get("/v1/public/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "has_more" in data

    @pytest.mark.asyncio
    async def test_directory_no_auth_required(self, client: AsyncClient):
        resp = await client.get("/v1/public/agents")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_directory_with_sort(self, client: AsyncClient):
        for sort in ["recent_active", "trust_first", "newest"]:
            resp = await client.get("/v1/public/agents", params={"sort": sort})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_directory_with_limit(self, client: AsyncClient):
        resp = await client.get("/v1/public/agents", params={"limit": 5})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) <= 5

    @pytest.mark.asyncio
    async def test_directory_search_query(self, client: AsyncClient):
        resp = await client.get("/v1/public/agents", params={"q": "translation"})
        assert resp.status_code == 200
        assert "data" in resp.json()

    @pytest.mark.asyncio
    async def test_directory_filter_skills(self, client: AsyncClient):
        resp = await client.get("/v1/public/agents", params={"skills": "translation,writing"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_directory_filter_languages(self, client: AsyncClient):
        resp = await client.get("/v1/public/agents", params={"languages": "en,zh-CN"})
        assert resp.status_code == 200


class TestPublicAgentCard:
    """Test GET /v1/public/agents/{slug}."""

    @pytest.mark.asyncio
    async def test_get_public_agent_card(self, client: AsyncClient):
        agent = await _make_public_service_agent(client, "public-card-agent")

        resp = await client.get(f"/v1/public/agents/{agent['slug']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == agent["id"]

    @pytest.mark.asyncio
    async def test_nonexistent_slug_returns_404(self, client: AsyncClient):
        resp = await client.get("/v1/public/agents/totally-nonexistent-slug-xyz")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_private_agent_not_in_public_card(self, client: AsyncClient):
        """Personal agents with network_only visibility should not appear."""
        agent = await _register(client, "public-card-private", "personal")
        resp = await client.get(f"/v1/public/agents/{agent['slug']}")
        # Personal agents default to network_only, should not be publicly visible
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_public_card_no_auth_required(self, client: AsyncClient):
        agent = await _make_public_service_agent(client, "public-card-noauth")
        resp = await client.get(f"/v1/public/agents/{agent['slug']}")
        assert resp.status_code == 200
