"""Tests for circle API routes — creation, join, leave, dissolve, transfer.

Covers spec §8 (circle system), §8.3 (hard constraints).
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
    data = resp.json()
    # Complete email verification so agent passes new-account restriction
    headers = {"Authorization": f"Bearer {data['api_key']}"}
    start = await client.post(
        "/v1/verifications/email/start",
        params={"email": f"{slug}@test.seabay.ai"},
        headers=headers,
    )
    start_data = start.json()
    await client.post(
        "/v1/verifications/email/complete",
        params={
            "verification_id": start_data["verification_id"],
            "code": start_data["_dev_code"],
        },
        headers=headers,
    )
    return data


async def _create_circle(
    client: AsyncClient,
    api_key: str,
    name: str = "Test Circle",
    max_members: int = 30,
    join_mode: str = "invite_only",
) -> dict:
    resp = await client.post(
        "/v1/circles",
        json={
            "name": name,
            "description": "A test circle",
            "join_mode": join_mode,
            "contact_mode": "request_only",
            "max_members": max_members,
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return resp.json()


class TestCreateCircle:
    """Test POST /v1/circles."""

    @pytest.mark.asyncio
    async def test_create_circle_valid(self, client: AsyncClient):
        owner = await _register(client, "circle-owner-1")
        resp = await client.post(
            "/v1/circles",
            json={
                "name": "My Circle",
                "join_mode": "invite_only",
                "contact_mode": "request_only",
            },
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Circle"
        assert data["owner_agent_id"] == owner["id"]
        assert data["member_count"] == 1
        assert data["is_active"] is True
        assert data["join_mode"] == "invite_only"

    @pytest.mark.asyncio
    async def test_max_members_enforced(self, client: AsyncClient):
        """max_members cannot exceed CIRCLE_MAX_MEMBERS (30)."""
        owner = await _register(client, "circle-owner-max")
        resp = await client.post(
            "/v1/circles",
            json={
                "name": "Big Circle",
                "max_members": 30,
            },
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["max_members"] <= 30

    @pytest.mark.asyncio
    async def test_max_members_request_over_30_rejected(self, client: AsyncClient):
        """Requesting max_members > 30 should be rejected by schema validation."""
        owner = await _register(client, "circle-owner-over30")
        resp = await client.post(
            "/v1/circles",
            json={
                "name": "Too Big",
                "max_members": 50,
            },
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        # Schema enforces le=30, so 422
        assert resp.status_code == 422


class TestGetCircle:
    """Test GET /v1/circles/{id}."""

    @pytest.mark.asyncio
    async def test_get_circle(self, client: AsyncClient):
        owner = await _register(client, "circle-getter-1")
        circle = await _create_circle(client, owner["api_key"], name="Get Test")
        resp = await client.get(
            f"/v1/circles/{circle['id']}",
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_circle(self, client: AsyncClient):
        owner = await _register(client, "circle-getter-2")
        resp = await client.get(
            "/v1/circles/nonexistent_id",
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 404


class TestJoinCircle:
    """Test POST /v1/circles/{id}/join."""

    @pytest.mark.asyncio
    async def test_join_invite_only_with_valid_token(self, client: AsyncClient):
        owner = await _register(client, "circle-join-owner-1")
        joiner = await _register(client, "circle-joiner-1")
        circle = await _create_circle(client, owner["api_key"])
        invite_token = circle["invite_link_token"]

        resp = await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": invite_token},
            headers={"Authorization": f"Bearer {joiner['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "joined"

    @pytest.mark.asyncio
    async def test_join_invite_only_without_token_fails(self, client: AsyncClient):
        owner = await _register(client, "circle-join-owner-2")
        joiner = await _register(client, "circle-joiner-2")
        circle = await _create_circle(client, owner["api_key"])

        resp = await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={},
            headers={"Authorization": f"Bearer {joiner['api_key']}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_join_open_link_with_token(self, client: AsyncClient):
        owner = await _register(client, "circle-openlink-owner")
        joiner = await _register(client, "circle-openlink-joiner")
        circle = await _create_circle(
            client, owner["api_key"], join_mode="open_link",
        )
        invite_token = circle["invite_link_token"]

        resp = await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": invite_token},
            headers={"Authorization": f"Bearer {joiner['api_key']}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_join_request_approve_redirects(self, client: AsyncClient):
        owner = await _register(client, "circle-reqapprove-owner")
        joiner = await _register(client, "circle-reqapprove-joiner")
        circle = await _create_circle(
            client, owner["api_key"], join_mode="request_approve",
        )

        resp = await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={},
            headers={"Authorization": f"Bearer {joiner['api_key']}"},
        )
        # Should get 400 saying to use join-requests endpoint
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cannot_join_twice(self, client: AsyncClient):
        owner = await _register(client, "circle-double-join-owner")
        joiner = await _register(client, "circle-double-joiner")
        circle = await _create_circle(client, owner["api_key"])
        token = circle["invite_link_token"]

        await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": token},
            headers={"Authorization": f"Bearer {joiner['api_key']}"},
        )
        resp = await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": token},
            headers={"Authorization": f"Bearer {joiner['api_key']}"},
        )
        assert resp.status_code == 409


class TestLeaveCircle:
    """Test POST /v1/circles/{id}/leave."""

    @pytest.mark.asyncio
    async def test_member_can_leave(self, client: AsyncClient):
        owner = await _register(client, "circle-leave-owner")
        member = await _register(client, "circle-leave-member")
        circle = await _create_circle(client, owner["api_key"])
        token = circle["invite_link_token"]

        # Join first
        await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": token},
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )

        # Leave
        resp = await client.post(
            f"/v1/circles/{circle['id']}/leave",
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "left"

    @pytest.mark.asyncio
    async def test_owner_cannot_leave(self, client: AsyncClient):
        owner = await _register(client, "circle-owner-noleave")
        circle = await _create_circle(client, owner["api_key"])

        resp = await client.post(
            f"/v1/circles/{circle['id']}/leave",
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 400


class TestDissolveCircle:
    """Test POST /v1/circles/{id}/dissolve."""

    @pytest.mark.asyncio
    async def test_owner_can_dissolve(self, client: AsyncClient):
        owner = await _register(client, "circle-dissolve-owner")
        circle = await _create_circle(client, owner["api_key"])

        resp = await client.post(
            f"/v1/circles/{circle['id']}/dissolve",
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dissolved"

    @pytest.mark.asyncio
    async def test_non_owner_cannot_dissolve(self, client: AsyncClient):
        owner = await _register(client, "circle-dissolve-owner2")
        member = await _register(client, "circle-dissolve-member")
        circle = await _create_circle(client, owner["api_key"])
        token = circle["invite_link_token"]

        await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": token},
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )

        resp = await client.post(
            f"/v1/circles/{circle['id']}/dissolve",
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )
        assert resp.status_code == 403


class TestTransferOwnership:
    """Test POST /v1/circles/{id}/transfer-ownership."""

    @pytest.mark.asyncio
    async def test_transfer_to_member(self, client: AsyncClient):
        owner = await _register(client, "circle-transfer-owner")
        member = await _register(client, "circle-transfer-member")
        circle = await _create_circle(client, owner["api_key"])
        token = circle["invite_link_token"]

        # Join as member
        await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": token},
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )

        # Transfer
        resp = await client.post(
            f"/v1/circles/{circle['id']}/transfer-ownership",
            params={"new_owner_id": member["id"]},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["new_owner_id"] == member["id"]

    @pytest.mark.asyncio
    async def test_transfer_to_non_member_fails(self, client: AsyncClient):
        owner = await _register(client, "circle-transfer-owner2")
        outsider = await _register(client, "circle-transfer-outsider")
        circle = await _create_circle(client, owner["api_key"])

        resp = await client.post(
            f"/v1/circles/{circle['id']}/transfer-ownership",
            params={"new_owner_id": outsider["id"]},
            headers={"Authorization": f"Bearer {owner['api_key']}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_non_owner_cannot_transfer(self, client: AsyncClient):
        owner = await _register(client, "circle-transfer-owner3")
        member = await _register(client, "circle-transfer-member2")
        circle = await _create_circle(client, owner["api_key"])
        token = circle["invite_link_token"]

        await client.post(
            f"/v1/circles/{circle['id']}/join",
            json={"invite_token": token},
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )

        resp = await client.post(
            f"/v1/circles/{circle['id']}/transfer-ownership",
            params={"new_owner_id": owner["id"]},
            headers={"Authorization": f"Bearer {member['api_key']}"},
        )
        assert resp.status_code == 403
