"""Integration tests for relationship lifecycle — edges, origins, strength.

Requires: PostgreSQL running locally (or set SEABAY_TEST_DATABASE_URL).
Run: pytest tests/integration/ -m integration
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_edge(db_session, sample_agent, sample_personal_agent):
    """Test creating a relationship edge."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    edge = await relationship_service.get_or_create_edge(
        db_session, agent_a.id, agent_b.id,
    )

    assert edge.from_agent_id == agent_a.id
    assert edge.to_agent_id == agent_b.id
    assert edge.strength == "new"
    assert edge.is_blocked is False


@pytest.mark.asyncio
async def test_edge_idempotent(db_session, sample_agent, sample_personal_agent):
    """Test that get_or_create_edge is idempotent."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    edge1 = await relationship_service.get_or_create_edge(
        db_session, agent_a.id, agent_b.id,
    )
    edge2 = await relationship_service.get_or_create_edge(
        db_session, agent_a.id, agent_b.id,
    )

    assert edge1.id == edge2.id


@pytest.mark.asyncio
async def test_add_origin(db_session, sample_agent, sample_personal_agent):
    """Test adding an origin to a relationship edge."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    edge = await relationship_service.get_or_create_edge(
        db_session, agent_a.id, agent_b.id,
    )

    origin = await relationship_service.add_origin(
        db_session, edge.id, "imported_contact",
    )

    assert origin.origin_type == "imported_contact"
    assert origin.origin_status == "active"


@pytest.mark.asyncio
async def test_block_agent(db_session, sample_agent, sample_personal_agent):
    """Test blocking an agent."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    await relationship_service.block_agent(
        db_session, agent_a.id, agent_b.id, block=True,
    )

    assert await relationship_service.is_blocked(
        db_session, agent_a.id, agent_b.id,
    ) is True


@pytest.mark.asyncio
async def test_unblock_agent(db_session, sample_agent, sample_personal_agent):
    """Test unblocking an agent."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    await relationship_service.block_agent(
        db_session, agent_a.id, agent_b.id, block=True,
    )
    await relationship_service.block_agent(
        db_session, agent_a.id, agent_b.id, block=False,
    )

    assert await relationship_service.is_blocked(
        db_session, agent_a.id, agent_b.id,
    ) is False


@pytest.mark.asyncio
async def test_has_any_relationship(db_session, sample_agent, sample_personal_agent):
    """Test checking for any relationship."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    assert await relationship_service.has_any_relationship(
        db_session, agent_a.id, agent_b.id,
    ) is False

    await relationship_service.get_or_create_edge(
        db_session, agent_a.id, agent_b.id,
    )

    assert await relationship_service.has_any_relationship(
        db_session, agent_a.id, agent_b.id,
    ) is True


@pytest.mark.asyncio
async def test_derive_strength_new(db_session, sample_agent, sample_personal_agent):
    """Test strength derivation for new relationship."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    strength = await relationship_service.derive_strength(
        db_session, agent_a.id, agent_b.id,
    )
    assert strength == "new"


@pytest.mark.asyncio
async def test_record_interaction(db_session, sample_agent, sample_personal_agent):
    """Test recording interaction on edge."""
    from app.services import relationship_service

    agent_a, _ = sample_agent
    agent_b, _ = sample_personal_agent

    await relationship_service.get_or_create_edge(
        db_session, agent_a.id, agent_b.id,
    )

    await relationship_service.record_interaction_on_edge(
        db_session, agent_a.id, agent_b.id, success=True, rating=5,
    )

    # Re-read the edge
    updated = await relationship_service.get_edge(
        db_session, agent_a.id, agent_b.id,
    )
    assert updated.interaction_count == 1
    assert updated.success_count == 1
