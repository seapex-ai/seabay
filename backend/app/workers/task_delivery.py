"""Task delivery worker — polls pending_delivery tasks and delivers via webhook.

Retry schedule per spec §12.4:
- Attempt 1: immediate
- Attempt 2: +1s delay
- Attempt 3: +5s delay
- Attempt 4: +25s delay
- After max attempts: status → failed
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.enums import TaskStatus
from app.models.task import Task
from app.services.webhook_service import deliver_task_to_agent

logger = logging.getLogger(__name__)

# Poll interval in seconds
POLL_INTERVAL = 5


async def run_delivery_worker(shutdown_event: asyncio.Event) -> None:
    """Main delivery worker loop. Runs until shutdown_event is set."""
    logger.info("Task delivery worker started")
    while not shutdown_event.is_set():
        try:
            await _process_pending_tasks()
        except Exception:
            logger.exception("Error in delivery worker")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=POLL_INTERVAL)
            break  # shutdown requested
        except asyncio.TimeoutError:
            continue  # poll again

    logger.info("Task delivery worker stopped")


async def _process_pending_tasks() -> None:
    """Process all pending_delivery tasks that are ready for delivery."""
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)

        # Get tasks that need delivery
        result = await db.execute(
            select(Task).where(
                Task.status == TaskStatus.PENDING_DELIVERY.value,
                Task.expires_at > now,
            ).where(
                # Either never attempted, or next_delivery_at has passed
                (Task.next_delivery_at.is_(None)) | (Task.next_delivery_at <= now)
            ).limit(50)  # batch size
        )
        tasks = result.scalars().all()

        for task in tasks:
            try:
                await deliver_task_to_agent(db, task)
            except Exception:
                logger.exception("Failed to deliver task %s", task.id)

        await db.commit()
