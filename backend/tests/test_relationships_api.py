"""Tests for relationship API routes — import, claim, list, star, block, introduce.

Covers spec §6 (multi-origin relationships), §7 (forming relationships).
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


class TestImportContact:
    """Test POST /v1/relationships/import."""

    @pytest.mark.asyncio
    async def test_import_contact_valid(self, client: AsyncClient):
        importer = await _register(client, "rel-importer-1")
        target = await _register(client, "rel-import-target-1")

        resp = await client.post(
            "/v1/relationships/import",
            json={
                "to_agent_id": target["id"],
                "origin_type": "imported_contact",
            },
            headers={"Authorization": f"Bearer {importer['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["from_agent_id"] == importer["id"]
        assert data["to_agent_id"] == target["id"]
        assert data["strength"] == "new"

    @pytest.mark.asyncio
    async def test_import_self_rejected(self, client: AsyncClient):
        agent = await _register(client, "rel-import-self")

        resp = await client.post(
            "/v1/relationships/import",
            json={
                "to_agent_id": agent["id"],
                "origin_type": "imported_contact",
            },
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_import_nonexistent_target(self, client: AsyncClient):
        importer = await _register(client, "rel-importer-noexist")

        resp = await client.post(
            "/v1/relationships/import",
            json={
                "to_agent_id": "nonexistent_agent",
                "origin_type": "imported_contact",
            },
            headers={"Authorization": f"Bearer {importer['api_key']}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_origin_rejected(self, client: AsyncClient):
        importer = await _register(client, "rel-importer-dup")
        target = await _register(client, "rel-import-target-dup")

        # First import
        await client.post(
            "/v1/relationships/import",
            json={
                "to_agent_id": target["id"],
                "origin_type": "imported_contact",
            },
            headers={"Authorization": f"Bearer {importer['api_key']}"},
        )
        # Second import (same origin)
        resp = await client.post(
            "/v1/relationships/import",
            json={
                "to_agent_id": target["id"],
                "origin_type": "imported_contact",
            },
            headers={"Authorization": f"Bearer {importer['api_key']}"},
        )
        assert resp.status_code == 409


class TestClaimByHandle:
    """Test POST /v1/relationships/claim."""

    @pytest.mark.asyncio
    async def test_claim_valid(self, client: AsyncClient):
        claimer = await _register(client, "rel-claimer-1")
        target = await _register(client, "rel-claim-target-1")

        resp = await client.post(
            "/v1/relationships/claim",
            json={
                "claim_value": target["slug"],
                "claim_type": "handle",
            },
            headers={"Authorization": f"Bearer {claimer['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["to_agent_id"] == target["id"]

    @pytest.mark.asyncio
    async def test_claim_nonexistent_handle(self, client: AsyncClient):
        claimer = await _register(client, "rel-claimer-noexist")

        resp = await client.post(
            "/v1/relationships/claim",
            json={
                "claim_value": "nonexistent-slug-xyz",
                "claim_type": "handle",
            },
            headers={"Authorization": f"Bearer {claimer['api_key']}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_claim_self_rejected(self, client: AsyncClient):
        agent = await _register(client, "rel-claim-self")

        resp = await client.post(
            "/v1/relationships/claim",
            json={
                "claim_value": agent["slug"],
                "claim_type": "handle",
            },
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 400


class TestListMyRelationships:
    """Test GET /v1/relationships/my."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        agent = await _register(client, "rel-list-empty")

        resp = await client.get(
            "/v1/relationships/my",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_list_after_import(self, client: AsyncClient):
        agent = await _register(client, "rel-list-agent")
        target = await _register(client, "rel-list-target")

        await client.post(
            "/v1/relationships/import",
            json={"to_agent_id": target["id"], "origin_type": "imported_contact"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )

        resp = await client.get(
            "/v1/relationships/my",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1


class TestGetRelationship:
    """Test GET /v1/relationships/{agent_id}."""

    @pytest.mark.asyncio
    async def test_get_bidirectional_view(self, client: AsyncClient):
        agent_a = await _register(client, "rel-bidi-a")
        agent_b = await _register(client, "rel-bidi-b")

        # A imports B
        await client.post(
            "/v1/relationships/import",
            json={"to_agent_id": agent_b["id"], "origin_type": "imported_contact"},
            headers={"Authorization": f"Bearer {agent_a['api_key']}"},
        )

        resp = await client.get(
            f"/v1/relationships/{agent_b['id']}",
            headers={"Authorization": f"Bearer {agent_a['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["me_to_them"] is not None
        assert data["me_to_them"]["to_agent_id"] == agent_b["id"]
        assert "mutual_circles" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_relationship(self, client: AsyncClient):
        agent = await _register(client, "rel-norel-agent")

        resp = await client.get(
            "/v1/relationships/nonexistent_agent_id",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 404


class TestStarUnstar:
    """Test PUT /v1/relationships/{agent_id}/star."""

    @pytest.mark.asyncio
    async def test_star_relationship(self, client: AsyncClient):
        agent = await _register(client, "rel-star-agent")
        target = await _register(client, "rel-star-target")

        # Create relationship first
        await client.post(
            "/v1/relationships/import",
            json={"to_agent_id": target["id"], "origin_type": "imported_contact"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )

        resp = await client.put(
            f"/v1/relationships/{target['id']}/star",
            json={"starred": True},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["starred"] is True

    @pytest.mark.asyncio
    async def test_unstar_relationship(self, client: AsyncClient):
        agent = await _register(client, "rel-unstar-agent")
        target = await _register(client, "rel-unstar-target")

        # Create and star
        await client.post(
            "/v1/relationships/import",
            json={"to_agent_id": target["id"], "origin_type": "imported_contact"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        await client.put(
            f"/v1/relationships/{target['id']}/star",
            json={"starred": True},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )

        # Unstar
        resp = await client.put(
            f"/v1/relationships/{target['id']}/star",
            json={"starred": False},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["starred"] is False

    @pytest.mark.asyncio
    async def test_star_nonexistent_relationship(self, client: AsyncClient):
        agent = await _register(client, "rel-star-norel")

        resp = await client.put(
            "/v1/relationships/nonexistent_id/star",
            json={"starred": True},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 404


class TestBlockUnblock:
    """Test POST /v1/relationships/{agent_id}/block."""

    @pytest.mark.asyncio
    async def test_block_agent(self, client: AsyncClient):
        blocker = await _register(client, "rel-blocker")
        target = await _register(client, "rel-block-target")

        resp = await client.post(
            f"/v1/relationships/{target['id']}/block",
            json={"block": True},
            headers={"Authorization": f"Bearer {blocker['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_blocked"] is True

    @pytest.mark.asyncio
    async def test_unblock_agent(self, client: AsyncClient):
        blocker = await _register(client, "rel-unblocker")
        target = await _register(client, "rel-unblock-target")

        # Block first
        await client.post(
            f"/v1/relationships/{target['id']}/block",
            json={"block": True},
            headers={"Authorization": f"Bearer {blocker['api_key']}"},
        )
        # Unblock
        resp = await client.post(
            f"/v1/relationships/{target['id']}/block",
            json={"block": False},
            headers={"Authorization": f"Bearer {blocker['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_blocked"] is False


class TestIntroduceAcceptDecline:
    """Test POST /v1/relationships/introduce and accept/decline."""

    @pytest.mark.asyncio
    async def test_introduce_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/relationships/introduce",
            json={
                "target_a_id": "agt_a",
                "target_b_id": "agt_b",
            },
        )
        assert resp.status_code == 422  # missing auth header
