"""Agent status decay worker — auto-transitions online status.

Per spec §15.1:
- If last_api_call < 5min ago: keep current status
- If last_api_call 5–30min ago: auto-set away (unless manually busy)
- If last_api_call > 30min: auto-set offline
- busy status never auto-downgrades
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.agent import Agent

logger = logging.getLogger(__name__)

# Check interval: every 5 minutes
CHECK_INTERVAL = 300


async def run_status_decay(shutdown_event: asyncio.Event) -> None:
    """Main status decay loop."""
    logger.info("Status decay worker started")
    while not shutdown_event.is_set():
        try:
            await _decay_agent_statuses()
        except Exception:
            logger.exception("Error in status decay worker")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=CHECK_INTERVAL)
            break
        except asyncio.TimeoutError:
            continue

    logger.info("Status decay worker stopped")


async def _decay_agent_statuses() -> None:
    """Check all active agents and decay their status based on last_seen_at."""
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)
        away_threshold = now - timedelta(seconds=settings.ONLINE_AWAY_THRESHOLD)
        offline_threshold = now - timedelta(seconds=settings.ONLINE_OFFLINE_THRESHOLD)

        # Get agents that are online or away (not busy, suspended, banned)
        result = await db.execute(
            select(Agent).where(
                Agent.status.in_(["online", "away"]),
                Agent.last_seen_at.isnot(None),
            )
        )
        agents = result.scalars().all()

        updated = 0
        for agent in agents:
            last_seen = agent.last_seen_at
            if isinstance(last_seen, str):
                try:
                    last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue

            if last_seen < offline_threshold:
                if agent.status != "offline":
                    agent.status = "offline"
                    updated += 1
            elif last_seen < away_threshold:
                if agent.status == "online":
                    agent.status = "away"
                    updated += 1

        if updated:
            await db.commit()
            logger.info("Decayed %d agent statuses", updated)
