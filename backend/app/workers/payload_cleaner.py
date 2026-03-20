"""Payload cleaner worker — removes payload data from old completed/failed/cancelled tasks.

Runs daily:
- Tasks in terminal states (completed, failed, cancelled) older than 90 days
  have payload_inline and payload_ref set to None.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.database import async_session_factory
from app.models.enums import TaskStatus
from app.models.task import Task

logger = logging.getLogger(__name__)

# Check interval: daily (24 hours)
CHECK_INTERVAL = 86400

# Payload retention: 90 days
PAYLOAD_RETENTION_DAYS = 90


async def run_payload_cleaner(shutdown_event: asyncio.Event) -> None:
    """Main payload cleaner loop. Runs until shutdown_event is set."""
    logger.info("Payload cleaner worker started")
    while not shutdown_event.is_set():
        try:
            await _clean_old_payloads()
        except Exception:
            logger.exception("Error in payload cleaner")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=CHECK_INTERVAL)
            break
        except asyncio.TimeoutError:
            continue

    logger.info("Payload cleaner worker stopped")


async def _clean_old_payloads() -> None:
    """Set payload_inline and payload_ref to None on old terminal tasks."""
    async with async_session_factory() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=PAYLOAD_RETENTION_DAYS)

        terminal_statuses = [
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        ]

        # Find tasks with payloads that need cleaning
        result = await db.execute(
            select(Task).where(
                Task.status.in_(terminal_statuses),
                Task.created_at <= cutoff,
                # Only select tasks that still have payload data
                (Task.payload_inline.isnot(None)) | (Task.payload_ref.isnot(None)),
            )
        )
        tasks = result.scalars().all()

        cleaned = 0
        for task in tasks:
            task.payload_inline = None
            task.payload_ref = None
            cleaned += 1

        if cleaned:
            await db.commit()
            logger.info("Cleaned payloads from %d old tasks (>%d days)", cleaned, PAYLOAD_RETENTION_DAYS)
