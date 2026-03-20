"""Integration tests for agent lifecycle — registration, update, search.

Requires: PostgreSQL running locally (or set SEABAY_TEST_DATABASE_URL).
Run: pytest tests/integration/ -m integration
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_agent_registration(db_session):
    """Test full agent registration flow."""
    from app.services import agent_service

    agent, api_key = await agent_service.register_agent(
        db_session,
        slug="integration-test-agent",
        display_name="Integration Test",
        bio="Testing agent",
        skills=["testing"],
    )

    assert agent.id.startswith("agt_")
    assert agent.slug == "integration-test-agent"
    assert agent.display_name == "Integration Test"
    assert api_key.startswith("sk_live_")
    assert agent.status == "offline"
    assert agent.verification_level == "none"


@pytest.mark.asyncio
async def test_agent_slug_uniqueness(db_session):
    """Test that duplicate slugs are rejected."""
    from app.core.exceptions import ConflictError
    from app.services import agent_service

    await agent_service.register_agent(
        db_session, slug="unique-slug-test", display_name="Agent 1",
    )

    with pytest.raises(ConflictError):
        await agent_service.register_agent(
            db_session, slug="unique-slug-test", display_name="Agent 2",
        )


@pytest.mark.asyncio
async def test_agent_update(db_session):
    """Test agent profile update."""
    from app.services import agent_service

    agent, _ = await agent_service.register_agent(
        db_session, slug="update-test-agent", display_name="Before Update",
    )

    updated = await agent_service.update_agent(
        db_session, agent, display_name="After Update",
    )

    assert updated.display_name == "After Update"


@pytest.mark.asyncio
async def test_agent_retrieval(db_session):
    """Test agent retrieval by ID."""
    from app.services import agent_service

    agent, _ = await agent_service.register_agent(
        db_session, slug="get-test-agent", display_name="Get Test",
    )

    retrieved = await agent_service.get_agent(db_session, agent.id)
    assert retrieved.id == agent.id
    assert retrieved.slug == "get-test-agent"


@pytest.mark.asyncio
async def test_agent_not_found(db_session):
    """Test agent retrieval with invalid ID."""
    from app.core.exceptions import NotFoundError
    from app.services import agent_service

    with pytest.raises(NotFoundError):
        await agent_service.get_agent(db_session, "agt_nonexistent")


@pytest.mark.asyncio
async def test_protected_brand_rejection(db_session):
    """Test that protected brand names are rejected."""
    from app.core.exceptions import InvalidRequestError
    from app.services import agent_service

    with pytest.raises(InvalidRequestError, match="protected brand"):
        await agent_service.register_agent(
            db_session,
            slug="brand-test",
            display_name="My ChatGPT Agent",
        )


@pytest.mark.asyncio
async def test_service_agent_defaults(db_session):
    """Test that service agents get public defaults."""
    from app.models.enums import AgentType
    from app.services import agent_service

    agent, _ = await agent_service.register_agent(
        db_session,
        slug="service-defaults-test",
        display_name="Service Agent",
        agent_type=AgentType.SERVICE,
    )

    assert agent.visibility_scope == "public"
    assert agent.contact_policy == "public_service_only"


@pytest.mark.asyncio
async def test_personal_agent_defaults(db_session):
    """Test that personal agents get network_only defaults."""
    from app.services import agent_service

    agent, _ = await agent_service.register_agent(
        db_session,
        slug="personal-defaults-test",
        display_name="Personal Agent",
    )

    assert agent.visibility_scope == "network_only"
    assert agent.contact_policy == "known_direct"
