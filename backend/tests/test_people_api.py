"""Tests for people matching API — Phase B controlled stranger matching.

Covers search, express_interest, verification enforcement.

Note: verification_level is NOT updatable via API (requires actual verification
flow), so express_interest tests verify the 403 enforcement for unverified agents.
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


class TestSearchPeople:
    """Test GET /v1/people/search."""

    @pytest.mark.asyncio
    async def test_search_requires_auth(self, client: AsyncClient):
        resp = await client.get("/v1/people/search")
        assert resp.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_search_returns_data(self, client: AsyncClient):
        agent = await _register(client, "people-searcher-1", agent_type="personal")
        resp = await client.get(
            "/v1/people/search",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert "data" in resp.json()

    @pytest.mark.asyncio
    async def test_search_with_filters(self, client: AsyncClient):
        agent = await _register(client, "people-filter-1", agent_type="personal")
        resp = await client.get(
            "/v1/people/search",
            params={
                "skills": "python,go",
                "languages": "en",
                "location_country": "US",
            },
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200


class TestExpressInterest:
    """Test POST /v1/people/interest.

    New agents have verification_level='none' by default. The service enforces
    email+ verification, so unverified agents correctly receive 403.
    """

    @pytest.mark.asyncio
    async def test_interest_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/people/interest",
            json={"target_agent_id": "some-id"},
        )
        assert resp.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_unverified_agent_gets_forbidden(self, client: AsyncClient):
        """Newly registered agents (verification_level=none) must be blocked."""
        from_agent = await _register(client, "interest-unverified", agent_type="personal")
        target = await _register(client, "interest-target-uv", agent_type="personal")
        resp = await client.post(
            "/v1/people/interest",
            json={"target_agent_id": target["id"]},
            headers={"Authorization": f"Bearer {from_agent['api_key']}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_interest_body_validation(self, client: AsyncClient):
        """Missing target_agent_id should fail validation."""
        agent = await _register(client, "interest-val-1", agent_type="personal")
        resp = await client.post(
            "/v1/people/interest",
            json={},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 422
