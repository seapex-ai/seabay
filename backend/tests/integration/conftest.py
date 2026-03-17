"""Integration test fixtures — shared database setup.

These fixtures use PostgreSQL (same as production) to ensure
type compatibility (ARRAY, JSONB). Set SEABAY_TEST_DATABASE_URL
or defaults to local dev database.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.agent import Base

# Must use PostgreSQL — models use ARRAY and JSONB which are pg-specific
TEST_DATABASE_URL = os.environ.get(
    "SEABAY_TEST_DATABASE_URL",
    "postgresql+asyncpg://seabay:seabay@localhost:5432/seabay_test",
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create an async engine for tests (PostgreSQL)."""
    try:
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session for each test.

    Each test gets its own transaction that is rolled back after.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def sample_agent(db_session: AsyncSession):
    """Create a sample agent for testing."""
    from app.core.id_generator import generate_id
    from app.core.security import generate_api_key, hash_api_key
    from app.models.agent import Agent, Profile

    agent_id = generate_id("agent")
    api_key = generate_api_key()

    agent = Agent(
        id=agent_id,
        slug=f"test-agent-{agent_id[-6:]}",
        display_name="Test Agent",
        agent_type="service",
        owner_type="individual",
        api_key_hash=hash_api_key(api_key),
        visibility_scope="public",
        contact_policy="public_service_only",
        status="online",
    )
    db_session.add(agent)

    profile = Profile(
        id=generate_id("profile"),
        agent_id=agent_id,
        bio="A test service agent",
        skills=["testing", "automation"],
        languages=["en"],
    )
    db_session.add(profile)
    await db_session.flush()

    return agent, api_key


@pytest_asyncio.fixture
async def sample_personal_agent(db_session: AsyncSession):
    """Create a sample personal agent for testing."""
    from app.core.id_generator import generate_id
    from app.core.security import generate_api_key, hash_api_key
    from app.models.agent import Agent, Profile

    agent_id = generate_id("agent")
    api_key = generate_api_key()

    agent = Agent(
        id=agent_id,
        slug=f"personal-{agent_id[-6:]}",
        display_name="Personal Agent",
        agent_type="personal",
        owner_type="individual",
        api_key_hash=hash_api_key(api_key),
        visibility_scope="network_only",
        contact_policy="known_direct",
        status="offline",
    )
    db_session.add(agent)

    profile = Profile(
        id=generate_id("profile"),
        agent_id=agent_id,
        bio="A personal test agent",
        skills=["general"],
        languages=["en", "zh"],
        location_country="US",
    )
    db_session.add(profile)
    await db_session.flush()

    return agent, api_key
