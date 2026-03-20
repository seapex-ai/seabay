"""Tests for intent API routes — create, get, matches, select, cancel.

Covers spec §11 (intent system), §13 (matching engine).
Uses the full ASGI client from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _register(
    client: AsyncClient,
    slug: str,
    agent_type: str = "service",
    visibility_scope: str | None = None,
) -> dict:
    resp = await client.post("/v1/agents/register", json={
        "slug": slug,
        "display_name": f"Test {slug}",
        "agent_type": agent_type,
    })
    data = resp.json()

    # Update visibility if needed (service agents can be public)
    if visibility_scope and agent_type == "service":
        await client.patch(
            f"/v1/agents/{data['id']}",
            json={"visibility_scope": visibility_scope},
            headers={"Authorization": f"Bearer {data['api_key']}"},
        )

    return data


async def _create_intent(
    client: AsyncClient,
    api_key: str,
    category: str = "service_request",
    description: str = "Need translation help",
    audience_scope: str = "public",
) -> dict:
    resp = await client.post(
        "/v1/intents",
        json={
            "category": category,
            "description": description,
            "structured_requirements": {"skills": ["translation"], "languages": ["en"]},
            "audience_scope": audience_scope,
            "ttl_hours": 72,
            "max_matches": 5,
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return resp


class TestCreateIntent:
    """Test POST /v1/intents."""

    @pytest.mark.asyncio
    async def test_create_intent_valid(self, client: AsyncClient):
        agent = await _register(client, "intent-creator-1")
        resp = await _create_intent(client, agent["api_key"])
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "active"
        assert data["category"] == "service_request"
        assert data["from_agent_id"] == agent["id"]
        assert data["ttl_hours"] == 72
        assert data["max_matches"] == 5

    @pytest.mark.asyncio
    async def test_create_intent_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/v1/intents",
            json={
                "category": "service_request",
                "description": "test",
            },
        )
        assert resp.status_code == 422  # missing auth header

    @pytest.mark.asyncio
    async def test_create_intent_invalid_category(self, client: AsyncClient):
        agent = await _register(client, "intent-creator-badcat")
        resp = await client.post(
            "/v1/intents",
            json={
                "category": "invalid_category",
                "description": "test",
            },
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_collaboration_intent(self, client: AsyncClient):
        agent = await _register(client, "intent-creator-collab")
        resp = await client.post(
            "/v1/intents",
            json={
                "category": "collaboration",
                "description": "Looking for a partner",
            },
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 201
        assert resp.json()["category"] == "collaboration"


class TestGetIntent:
    """Test GET /v1/intents/{id}."""

    @pytest.mark.asyncio
    async def test_get_intent(self, client: AsyncClient):
        agent = await _register(client, "intent-getter-1")
        create_resp = await _create_intent(client, agent["api_key"])
        intent_id = create_resp.json()["id"]

        resp = await client.get(
            f"/v1/intents/{intent_id}",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == intent_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_intent(self, client: AsyncClient):
        agent = await _register(client, "intent-getter-2")
        resp = await client.get(
            "/v1/intents/nonexistent_id",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 404


class TestGetMatches:
    """Test GET /v1/intents/{id}/matches."""

    @pytest.mark.asyncio
    async def test_get_matches_returns_list(self, client: AsyncClient):
        agent = await _register(client, "intent-matcher-1")
        create_resp = await _create_intent(client, agent["api_key"])
        intent_id = create_resp.json()["id"]

        resp = await client.get(
            f"/v1/intents/{intent_id}/matches",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_get_matches_only_own_intent(self, client: AsyncClient):
        creator = await _register(client, "intent-match-creator")
        other = await _register(client, "intent-match-other")
        create_resp = await _create_intent(client, creator["api_key"])
        intent_id = create_resp.json()["id"]

        resp = await client.get(
            f"/v1/intents/{intent_id}/matches",
            headers={"Authorization": f"Bearer {other['api_key']}"},
        )
        assert resp.status_code == 400


class TestSelectMatch:
    """Test POST /v1/intents/{id}/select."""

    @pytest.mark.asyncio
    async def test_select_nonexistent_intent(self, client: AsyncClient):
        agent = await _register(client, "intent-select-1")
        resp = await client.post(
            "/v1/intents/nonexistent_id/select",
            json={"agent_id": "some_agent"},
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 404


class TestCancelIntent:
    """Test POST /v1/intents/{id}/cancel."""

    @pytest.mark.asyncio
    async def test_cancel_own_intent(self, client: AsyncClient):
        agent = await _register(client, "intent-canceller-1")
        create_resp = await _create_intent(client, agent["api_key"])
        intent_id = create_resp.json()["id"]

        resp = await client.post(
            f"/v1/intents/{intent_id}/cancel",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cannot_cancel_others_intent(self, client: AsyncClient):
        creator = await _register(client, "intent-cancel-creator")
        other = await _register(client, "intent-cancel-other")
        create_resp = await _create_intent(client, creator["api_key"])
        intent_id = create_resp.json()["id"]

        resp = await client.post(
            f"/v1/intents/{intent_id}/cancel",
            headers={"Authorization": f"Bearer {other['api_key']}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cannot_cancel_already_cancelled(self, client: AsyncClient):
        agent = await _register(client, "intent-cancel-twice")
        create_resp = await _create_intent(client, agent["api_key"])
        intent_id = create_resp.json()["id"]

        # Cancel once
        await client.post(
            f"/v1/intents/{intent_id}/cancel",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        # Cancel again
        resp = await client.post(
            f"/v1/intents/{intent_id}/cancel",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        assert resp.status_code == 400
