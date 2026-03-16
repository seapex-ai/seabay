"""Test agent registration and management."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_service_agent(client: AsyncClient):
    response = await client.post("/v1/agents/register", json={
        "slug": "test-translator",
        "display_name": "Test Translation Service",
        "agent_type": "service",
        "bio": "Professional translation service",
        "skills": ["translation", "writing"],
        "languages": ["en", "zh-CN"],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "test-translator"
    assert data["agent_type"] == "service"
    assert "api_key" in data
    assert data["api_key"].startswith("sk_live_")


@pytest.mark.asyncio
async def test_register_personal_agent(client: AsyncClient):
    response = await client.post("/v1/agents/register", json={
        "slug": "test-alice",
        "display_name": "Alice's Agent",
        "agent_type": "personal",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["agent_type"] == "personal"


@pytest.mark.asyncio
async def test_register_duplicate_slug(client: AsyncClient):
    await client.post("/v1/agents/register", json={
        "slug": "dup-test",
        "display_name": "First",
        "agent_type": "personal",
    })
    response = await client.post("/v1/agents/register", json={
        "slug": "dup-test",
        "display_name": "Second",
        "agent_type": "personal",
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_agent_authenticated(client: AsyncClient):
    # Register
    reg = await client.post("/v1/agents/register", json={
        "slug": "test-get-agent",
        "display_name": "Get Agent Test",
        "agent_type": "service",
    })
    data = reg.json()
    api_key = data["api_key"]
    agent_id = data["id"]

    # Get
    response = await client.get(
        f"/v1/agents/{agent_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert response.status_code == 200
    agent = response.json()
    assert agent["id"] == agent_id
    assert agent["slug"] == "test-get-agent"


@pytest.mark.asyncio
async def test_update_agent(client: AsyncClient):
    reg = await client.post("/v1/agents/register", json={
        "slug": "test-update-agent",
        "display_name": "Update Test",
        "agent_type": "service",
    })
    data = reg.json()

    response = await client.patch(
        f"/v1/agents/{data['id']}",
        json={"display_name": "Updated Name", "bio": "New bio"},
        headers={"Authorization": f"Bearer {data['api_key']}"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_unauthorized_request(client: AsyncClient):
    response = await client.get(
        "/v1/agents/some-id",
        headers={"Authorization": "Bearer invalid_key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_personal_cannot_set_public_visibility(client: AsyncClient):
    """Personal agents cannot set visibility_scope=public."""
    reg = await client.post("/v1/agents/register", json={
        "slug": "test-personal-vis",
        "display_name": "Personal Vis Test",
        "agent_type": "personal",
    })
    data = reg.json()

    response = await client.patch(
        f"/v1/agents/{data['id']}",
        json={"visibility_scope": "public"},
        headers={"Authorization": f"Bearer {data['api_key']}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_personal_cannot_use_public_service_only(client: AsyncClient):
    """Personal agents cannot set contact_policy=public_service_only."""
    reg = await client.post("/v1/agents/register", json={
        "slug": "test-personal-cp",
        "display_name": "Personal CP Test",
        "agent_type": "personal",
    })
    data = reg.json()

    response = await client.patch(
        f"/v1/agents/{data['id']}",
        json={"contact_policy": "public_service_only"},
        headers={"Authorization": f"Bearer {data['api_key']}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_well_known_returns_404_for_nonexistent(client: AsyncClient):
    """A2A well-known endpoint returns 404 for unknown agents."""
    response = await client.get("/.well-known/agent-card/nonexistent.json")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_well_known_returns_404_for_non_public(client: AsyncClient):
    """A2A well-known endpoint returns 404 for non-public agents."""
    reg = await client.post("/v1/agents/register", json={
        "slug": "test-private-a2a",
        "display_name": "Private A2A Test",
        "agent_type": "personal",
    })
    data = reg.json()

    # Personal agents default to network_only, not public
    response = await client.get(f"/.well-known/agent-card/{data['id']}.json")
    assert response.status_code == 404
