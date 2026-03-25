"""Tests for people matching API — Phase B controlled stranger matching.

Covers search, express_interest, verification checks.
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


async def _register_personal(
    client: AsyncClient,
    slug: str,
    visibility: str = "public",
    verification: str = "email",
) -> dict:
    """Register a personal agent suitable for people matching."""
    agent = await _register(client, slug, agent_type="personal")
    # Update visibility and verification to make discoverable
    await client.patch(
        f"/v1/agents/{agent['id']}",
        json={
            "visibility_scope": visibility,
            "verification_level": verification,
        },
        headers={"Authorization": f"Bearer {agent['api_key']}"},
    )
    return agent


class TestSearchPeople:
    """Test GET /v1/people/search."""

    @pytest.mark.asyncio
    async def test_search_requires_auth(self, client: AsyncClient):
        resp = await client.get("/v1/people/search")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_search_returns_data(self, client: AsyncClient):
        searcher = await _register_personal(client, "people-searcher-1")
        resp = await client.get(
            "/v1/people/search",
            headers={"Authorization": f"Bearer {searcher['api_key']}"},
        )
        assert resp.status_code == 200
        assert "data" in resp.json()

    @pytest.mark.asyncio
    async def test_search_with_filters(self, client: AsyncClient):
        searcher = await _register_personal(client, "people-filter-1")
        resp = await client.get(
            "/v1/people/search",
            params={
                "skills": "python,go",
                "languages": "en",
                "location_country": "US",
            },
            headers={"Authorization": f"Bearer {searcher['api_key']}"},
        )
        assert resp.status_code == 200


class TestExpressInterest:
    """Test POST /v1/people/interest."""

    @pytest.mark.asyncio
    async def test_express_interest_success(self, client: AsyncClient):
        from_agent = await _register_personal(client, "interest-from-1")
        target = await _register_personal(client, "interest-target-1")
        resp = await client.post(
            "/v1/people/interest",
            json={
                "target_agent_id": target["id"],
                "message": "Would love to connect!",
            },
            headers={"Authorization": f"Bearer {from_agent['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "interest_recorded"

    @pytest.mark.asyncio
    async def test_interest_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/people/interest",
            json={"target_agent_id": "some-id"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_interest_target_not_found(self, client: AsyncClient):
        agent = await _register_personal(client, "interest-nf-1")
        resp = await client.post(
            "/v1/people/interest",
            json={"target_agent_id": "nonexistent"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_interest_target_must_be_personal(self, client: AsyncClient):
        from_agent = await _register_personal(client, "interest-type-from")
        service_agent = await _register(client, "interest-type-svc", agent_type="service")
        resp = await client.post(
            "/v1/people/interest",
            json={"target_agent_id": service_agent["id"]},
            headers={"Authorization": f"Bearer {from_agent['api_key']}"},
        )
        assert resp.status_code == 400
