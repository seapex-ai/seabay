"""Relationship strength re-derivation worker.

Periodically recalculates relationship strength for all active edges
based on current interaction data (spec §6.5).

Runs every 30 minutes.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session_factory
from app.models.relationship import RelationshipEdge
from app.services import relationship_service

logger = logging.getLogger(__name__)

# Check interval: every 30 minutes
CHECK_INTERVAL = 1800


async def run_strength_deriver(shutdown_event: asyncio.Event) -> None:
    """Main strength derivation loop."""
    logger.info("Strength deriver worker started")
    while not shutdown_event.is_set():
        try:
            await _rederive_all_strengths()
        except Exception:
            logger.exception("Error in strength deriver")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=CHECK_INTERVAL)
            break
        except asyncio.TimeoutError:
            continue

    logger.info("Strength deriver worker stopped")


async def _rederive_all_strengths() -> None:
    """Re-derive strength for all non-blocked edges with interactions."""
    async with async_session_factory() as db:
        # Get edges with at least 1 interaction
        result = await db.execute(
            select(RelationshipEdge).where(
                RelationshipEdge.is_blocked == False,  # noqa: E712
                RelationshipEdge.interaction_count > 0,
            ).limit(500)  # batch size
        )
        edges = result.scalars().all()

        updated = 0
        for edge in edges:
            new_strength = await relationship_service.derive_strength(
                db, edge.from_agent_id, edge.to_agent_id,
            )
            if edge.strength != new_strength:
                edge.strength = new_strength
                updated += 1

        if updated:
            await db.commit()
            logger.info("Re-derived %d/%d edge strengths", updated, len(edges))
