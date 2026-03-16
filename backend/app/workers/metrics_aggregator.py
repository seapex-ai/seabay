"""Daily metrics aggregation worker.

Runs once daily (at midnight UTC) to compute trust and popularity
metric snapshots for all active agents.

Also cleans up expired idempotency records.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete

from app.database import async_session_factory
from app.models.metrics import IdempotencyRecord
from app.services.metrics_service import aggregate_all_metrics

logger = logging.getLogger(__name__)

# Run daily: 24h = 86400s. In practice, runs at startup then every 24h.
RUN_INTERVAL = 86400


async def run_metrics_aggregator(shutdown_event: asyncio.Event) -> None:
    """Main metrics aggregation loop. Runs daily."""
    logger.info("Metrics aggregator worker started")

    # Initial delay: wait 60s after startup to let DB connections settle
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=60)
        return  # shutdown requested during initial delay
    except asyncio.TimeoutError:
        pass

    while not shutdown_event.is_set():
        try:
            await _run_daily_aggregation()
            await _cleanup_expired_idempotency()
        except Exception:
            logger.exception("Error in metrics aggregator")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=RUN_INTERVAL)
            break
        except asyncio.TimeoutError:
            continue

    logger.info("Metrics aggregator worker stopped")


async def _run_daily_aggregation() -> None:
    """Compute metrics for all agents."""
    async with async_session_factory() as db:
        count = await aggregate_all_metrics(db)
        await db.commit()
        logger.info("Aggregated daily metrics for %d agents", count)


async def _cleanup_expired_idempotency() -> None:
    """Remove expired idempotency records to keep table small."""
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.expires_at < now,
            )
        )
        if result.rowcount:
            await db.commit()
            logger.info("Cleaned up %d expired idempotency records", result.rowcount)
