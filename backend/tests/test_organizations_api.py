"""Tests for organization API — Phase C enterprise management.

Covers CRUD, membership, policies, permission checks.
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


async def _create_org(
    client: AsyncClient,
    api_key: str,
    slug: str = "test-org",
    display_name: str = "Test Org",
) -> dict:
    resp = await client.post(
        "/v1/organizations",
        json={
            "slug": slug,
            "display_name": display_name,
            "description": "A test organization",
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return resp.json()


class TestCreateOrg:
    """Test POST /v1/organizations."""

    @pytest.mark.asyncio
    async def test_create_org(self, client: AsyncClient):
        agent = await _register(client, "org-creator-1")
        resp = await client.post(
            "/v1/organizations",
            json={
                "slug": "my-org",
                "display_name": "My Organization",
                "description": "Test org",
                "domain": "example.com",
            },
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "my-org"
        assert data["display_name"] == "My Organization"
        assert data["owner_agent_id"] == agent["id"]
        assert data["status"] == "active"
        assert data["max_members"] == 100

    @pytest.mark.asyncio
    async def test_slug_uniqueness(self, client: AsyncClient):
        agent = await _register(client, "org-dup-1")
        await _create_org(client, agent["api_key"], slug="dup-slug")
        resp = await client.post(
            "/v1/organizations",
            json={"slug": "dup-slug", "display_name": "Dup"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/organizations",
            json={"slug": "no-auth", "display_name": "Fail"},
        )
        assert resp.status_code in (401, 403, 422)


class TestGetOrg:
    """Test GET /v1/organizations/{org_id}."""

    @pytest.mark.asyncio
    async def test_get_org(self, client: AsyncClient):
        agent = await _register(client, "org-getter-1")
        org = await _create_org(client, agent["api_key"], slug="get-org")
        resp = await client.get(f"/v1/organizations/{org['id']}")
        assert resp.status_code == 200
        assert resp.json()["slug"] == "get-org"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get("/v1/organizations/nonexistent")
        assert resp.status_code == 404


class TestUpdateOrg:
    """Test PATCH /v1/organizations/{org_id}."""

    @pytest.mark.asyncio
    async def test_update_by_owner(self, client: AsyncClient):
        agent = await _register(client, "org-updater-1")
        org = await _create_org(client, agent["api_key"], slug="upd-org")
        resp = await client.patch(
            f"/v1/organizations/{org['id']}",
            json={"display_name": "Updated Name"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_by_non_member(self, client: AsyncClient):
        owner = await _register(client, "org-upd-owner")
        other = await _register(client, "org-upd-other")
        org = await _create_org(client, owner["api_key"], slug="upd-perm")
        resp = await client.patch(
            f"/v1/organizations/{org['id']}",
            json={"display_name": "Hijack"},
            headers={"Authorization": f"Bearer {other['api_key']}"},
        )
        assert resp.status_code == 403


class TestMembership:
    """Test membership endpoints."""

    @pytest.mark.asyncio
    async def test_add_member(self, client: AsyncClient):
        owner = await _register(client, "org-mem-owner")
        member = await _register(client, "org-mem-new")
        org = await _create_org(client, owner["api_key"], slug="mem-org")
        resp = await client.post(
            f"/v1/organizations/{org['id']}/members",
            json={"agent_id": member["id"], "role": "member"},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 201
        assert resp.json()["agent_id"] == member["id"]
        assert resp.json()["role"] == "member"

    @pytest.mark.asyncio
    async def test_duplicate_member(self, client: AsyncClient):
        owner = await _register(client, "org-dup-mem-o")
        member = await _register(client, "org-dup-mem-m")
        org = await _create_org(client, owner["api_key"], slug="dup-mem-org")
        await client.post(
            f"/v1/organizations/{org['id']}/members",
            json={"agent_id": member["id"]},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        resp = await client.post(
            f"/v1/organizations/{org['id']}/members",
            json={"agent_id": member["id"]},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_members(self, client: AsyncClient):
        owner = await _register(client, "org-list-mem-o")
        org = await _create_org(client, owner["api_key"], slug="list-mem-org")
        resp = await client.get(f"/v1/organizations/{org['id']}/members")
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Owner auto-added
        assert len(data) >= 1
        assert data[0]["role"] == "owner"

    @pytest.mark.asyncio
    async def test_remove_member(self, client: AsyncClient):
        owner = await _register(client, "org-rm-mem-o")
        member = await _register(client, "org-rm-mem-m")
        org = await _create_org(client, owner["api_key"], slug="rm-mem-org")
        await client.post(
            f"/v1/organizations/{org['id']}/members",
            json={"agent_id": member["id"]},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        resp = await client.delete(
            f"/v1/organizations/{org['id']}/members/{member['id']}",
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_cannot_remove_owner(self, client: AsyncClient):
        owner = await _register(client, "org-rm-owner")
        org = await _create_org(client, owner["api_key"], slug="rm-owner-org")
        resp = await client.delete(
            f"/v1/organizations/{org['id']}/members/{owner['id']}",
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_cannot_add(self, client: AsyncClient):
        owner = await _register(client, "org-noadd-o")
        member = await _register(client, "org-noadd-m")
        newcomer = await _register(client, "org-noadd-n")
        org = await _create_org(client, owner["api_key"], slug="noadd-org")
        await client.post(
            f"/v1/organizations/{org['id']}/members",
            json={"agent_id": member["id"], "role": "member"},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        resp = await client.post(
            f"/v1/organizations/{org['id']}/members",
            json={"agent_id": newcomer["id"]},
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )
        assert resp.status_code == 403


class TestPolicies:
    """Test policy endpoints."""

    @pytest.mark.asyncio
    async def test_set_policy(self, client: AsyncClient):
        owner = await _register(client, "org-pol-owner")
        org = await _create_org(client, owner["api_key"], slug="pol-org")
        resp = await client.post(
            f"/v1/organizations/{org['id']}/policies",
            json={
                "policy_type": "access",
                "policy_key": "require_verification",
                "policy_value": "email",
            },
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_type"] == "access"
        assert data["policy_key"] == "require_verification"

    @pytest.mark.asyncio
    async def test_policy_upsert(self, client: AsyncClient):
        owner = await _register(client, "org-pol-ups-o")
        org = await _create_org(client, owner["api_key"], slug="pol-ups-org")
        headers = {"Authorization": f"Bearer {owner['api_key']}"}
        policy_data = {
            "policy_type": "access",
            "policy_key": "max_tasks",
            "policy_value": "10",
        }
        await client.post(f"/v1/organizations/{org['id']}/policies", json=policy_data, headers=headers)
        policy_data["policy_value"] = "20"
        resp = await client.post(f"/v1/organizations/{org['id']}/policies", json=policy_data, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["policy_value"] == "20"

    @pytest.mark.asyncio
    async def test_list_policies(self, client: AsyncClient):
        owner = await _register(client, "org-pol-list-o")
        org = await _create_org(client, owner["api_key"], slug="pol-list-org")
        headers = {"Authorization": f"Bearer {owner['api_key']}"}
        await client.post(
            f"/v1/organizations/{org['id']}/policies",
            json={"policy_type": "a", "policy_key": "k1", "policy_value": "v1"},
            headers=headers,
        )
        resp = await client.get(f"/v1/organizations/{org['id']}/policies")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    @pytest.mark.asyncio
    async def test_policy_requires_admin(self, client: AsyncClient):
        owner = await _register(client, "org-pol-perm-o")
        member = await _register(client, "org-pol-perm-m")
        org = await _create_org(client, owner["api_key"], slug="pol-perm-org")
        await client.post(
            f"/v1/organizations/{org['id']}/members",
            json={"agent_id": member["id"], "role": "member"},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        resp = await client.post(
            f"/v1/organizations/{org['id']}/policies",
            json={"policy_type": "a", "policy_key": "k", "policy_value": "v"},
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )
        assert resp.status_code == 403
