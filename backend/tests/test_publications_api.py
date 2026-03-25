"""Tests for publication API routes — Phase B.

Covers CRUD, search, /mine route, ownership validation.
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


async def _create_pub(
    client: AsyncClient,
    api_key: str,
    title: str = "Test Service",
    publication_type: str = "service",
) -> dict:
    resp = await client.post(
        "/v1/publications",
        json={
            "publication_type": publication_type,
            "title": title,
            "description": "A test publication",
            "tags": ["test", "demo"],
            "category": "dev-tools",
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return resp.json()


class TestCreatePublication:
    """Test POST /v1/publications."""

    @pytest.mark.asyncio
    async def test_create_service(self, client: AsyncClient):
        agent = await _register(client, "pub-creator-1")
        resp = await client.post(
            "/v1/publications",
            json={
                "publication_type": "service",
                "title": "My API Service",
                "description": "Provides data processing",
                "tags": ["api", "data"],
                "category": "data",
                "location_country": "US",
            },
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["publication_type"] == "service"
        assert data["title"] == "My API Service"
        assert data["agent_id"] == agent["id"]
        assert data["status"] == "active"
        assert data["visibility_scope"] == "public"
        assert data["view_count"] == 0

    @pytest.mark.asyncio
    async def test_create_all_types(self, client: AsyncClient):
        agent = await _register(client, "pub-creator-types")
        for pub_type in ("service", "product", "project_opening", "event", "exchange", "request"):
            resp = await client.post(
                "/v1/publications",
                json={
                    "publication_type": pub_type,
                    "title": f"Test {pub_type}",
                    "description": f"A {pub_type} listing",
                },
                headers={"Authorization": f"Bearer {agent['api_key']}"},
            )
            assert resp.status_code == 201, f"Failed for type: {pub_type}"

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/publications",
            json={
                "publication_type": "service",
                "title": "No Auth",
                "description": "Should fail",
            },
        )
        assert resp.status_code in (401, 403)


class TestGetPublication:
    """Test GET /v1/publications/{pub_id}."""

    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient):
        agent = await _register(client, "pub-getter-1")
        pub = await _create_pub(client, agent["api_key"])
        resp = await client.get(f"/v1/publications/{pub['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == pub["id"]

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get("/v1/publications/nonexistent")
        assert resp.status_code == 404


class TestUpdatePublication:
    """Test PATCH /v1/publications/{pub_id}."""

    @pytest.mark.asyncio
    async def test_update_title(self, client: AsyncClient):
        agent = await _register(client, "pub-updater-1")
        pub = await _create_pub(client, agent["api_key"])
        resp = await client.patch(
            f"/v1/publications/{pub['id']}",
            json={"title": "Updated Title"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_not_owner(self, client: AsyncClient):
        owner = await _register(client, "pub-update-owner")
        other = await _register(client, "pub-update-other")
        pub = await _create_pub(client, owner["api_key"])
        resp = await client.patch(
            f"/v1/publications/{pub['id']}",
            json={"title": "Hijack"},
            headers={"Authorization": f"Bearer {other['api_key']}"},
        )
        assert resp.status_code == 403


class TestDeletePublication:
    """Test DELETE /v1/publications/{pub_id}."""

    @pytest.mark.asyncio
    async def test_delete_own(self, client: AsyncClient):
        agent = await _register(client, "pub-deleter-1")
        pub = await _create_pub(client, agent["api_key"])
        resp = await client.delete(
            f"/v1/publications/{pub['id']}",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 204
        # Verify gone
        resp2 = await client.get(f"/v1/publications/{pub['id']}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_owner(self, client: AsyncClient):
        owner = await _register(client, "pub-del-owner")
        other = await _register(client, "pub-del-other")
        pub = await _create_pub(client, owner["api_key"])
        resp = await client.delete(
            f"/v1/publications/{pub['id']}",
            headers={"Authorization": f"Bearer {other['api_key']}"},
        )
        assert resp.status_code == 403


class TestListPublications:
    """Test GET /v1/publications (public search)."""

    @pytest.mark.asyncio
    async def test_list_returns_active_public(self, client: AsyncClient):
        agent = await _register(client, "pub-lister-1")
        await _create_pub(client, agent["api_key"], title="Searchable Pub")
        resp = await client.get("/v1/publications")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "has_more" in data

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self, client: AsyncClient):
        agent = await _register(client, "pub-lister-type")
        await _create_pub(client, agent["api_key"], publication_type="product", title="A Product")
        resp = await client.get("/v1/publications", params={"publication_type": "product"})
        assert resp.status_code == 200
        for item in resp.json()["data"]:
            assert item["publication_type"] == "product"


class TestMyPublications:
    """Test GET /v1/publications/mine — must NOT be shadowed by /{pub_id}."""

    @pytest.mark.asyncio
    async def test_mine_returns_own(self, client: AsyncClient):
        agent = await _register(client, "pub-mine-1")
        pub = await _create_pub(client, agent["api_key"], title="My Own Pub")
        resp = await client.get(
            "/v1/publications/mine",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        ids = [p["id"] for p in data["data"]]
        assert pub["id"] in ids

    @pytest.mark.asyncio
    async def test_mine_requires_auth(self, client: AsyncClient):
        resp = await client.get("/v1/publications/mine")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_mine_not_shadowed(self, client: AsyncClient):
        """Ensure /mine is not intercepted by /{pub_id} with pub_id='mine'."""
        agent = await _register(client, "pub-mine-shadow")
        resp = await client.get(
            "/v1/publications/mine",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        # Should return list, not a 404 from trying to find pub_id="mine"
        assert resp.status_code == 200
        assert "data" in resp.json()
