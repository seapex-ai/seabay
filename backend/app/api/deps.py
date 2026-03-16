"""API dependencies: authentication, rate limiting, DB session."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import UnauthorizedError
from app.core.security import extract_key_prefix, verify_api_key
from app.database import get_db
from app.models.agent import Agent


async def get_current_agent(
    authorization: str = Header(..., description="Bearer sk_live_xxx"),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Extract and verify API key from Authorization header.

    Uses api_key_prefix index for O(1) lookup when available,
    falls back to full scan for agents without prefix (pre-migration).
    Also updates last_seen_at for status decay tracking.
    """
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Authorization header must use Bearer scheme")

    api_key = authorization[7:]  # strip "Bearer "
    if not api_key.startswith("sk_live_"):
        raise UnauthorizedError("Invalid API key format")

    prefix = extract_key_prefix(api_key)

    # Fast path: lookup by prefix index (O(1) instead of O(n))
    result = await db.execute(
        select(Agent).options(selectinload(Agent.profile)).where(
            Agent.api_key_prefix == prefix,
        )
    )
    agent = result.scalar_one_or_none()
    if agent and verify_api_key(api_key, agent.api_key_hash):
        return _activate_agent(agent)

    # Fallback: scan agents without prefix (pre-migration compatibility)
    result = await db.execute(
        select(Agent).options(selectinload(Agent.profile)).where(
            Agent.api_key_prefix.is_(None),
            Agent.api_key_hash.isnot(None),
        )
    )
    for agent in result.scalars().all():
        if verify_api_key(api_key, agent.api_key_hash):
            # Backfill prefix on first successful auth
            agent.api_key_prefix = prefix
            return _activate_agent(agent)

    raise UnauthorizedError("Invalid API key")


def _activate_agent(agent: Agent) -> Agent:
    """Check status and update last_seen for an authenticated agent."""
    if agent.status in ("suspended", "banned"):
        raise UnauthorizedError(f"Agent is {agent.status}")
    agent.last_seen_at = datetime.now(timezone.utc)
    if agent.status in ("offline", "away"):
        agent.status = "online"
    return agent
