"""TTL checker worker — expires tasks, intents, introductions that exceeded TTL.

Runs hourly per spec:
- Tasks: if now > expires_at → status = expired
- Tasks waiting human confirm: if now > human_confirm_deadline → expired
- Intents: if now > expires_at → status = expired
- Introductions: if now > expires_at → status = expired
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.enums import TaskStatus
from app.models.intent import Intent
from app.models.introduction import Introduction
from app.models.task import Task

logger = logging.getLogger(__name__)

# Check interval: hourly
CHECK_INTERVAL = 3600


async def run_ttl_checker(shutdown_event: asyncio.Event) -> None:
    """Main TTL checker loop. Runs until shutdown_event is set."""
    logger.info("TTL checker worker started")
    while not shutdown_event.is_set():
        try:
            await _check_expired_tasks()
            await _check_expired_intents()
            await _check_expired_introductions()
        except Exception:
            logger.exception("Error in TTL checker")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=CHECK_INTERVAL)
            break
        except asyncio.TimeoutError:
            continue

    logger.info("TTL checker worker stopped")


async def _check_expired_tasks() -> None:
    """Expire tasks that have exceeded their TTL."""
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)

        # Non-terminal task statuses
        active_statuses = [
            TaskStatus.PENDING_DELIVERY.value,
            TaskStatus.DELIVERED.value,
            TaskStatus.PENDING_ACCEPT.value,
            TaskStatus.ACCEPTED.value,
            TaskStatus.IN_PROGRESS.value,
        ]

        # Expire tasks past expires_at
        result = await db.execute(
            select(Task).where(
                Task.status.in_(active_statuses),
                Task.expires_at <= now,
            )
        )
        tasks = result.scalars().all()
        for task in tasks:
            task.status = TaskStatus.EXPIRED.value
            logger.info("Task %s expired (TTL exceeded)", task.id)

        # Expire tasks waiting for human confirm past deadline
        confirm_result = await db.execute(
            select(Task).where(
                Task.status == TaskStatus.WAITING_HUMAN_CONFIRM.value,
                Task.human_confirm_deadline <= now,
            )
        )
        confirm_tasks = confirm_result.scalars().all()
        for task in confirm_tasks:
            task.status = TaskStatus.EXPIRED.value
            logger.info("Task %s expired (human confirm timeout)", task.id)

        if tasks or confirm_tasks:
            await db.commit()
            logger.info(
                "Expired %d tasks (TTL) and %d tasks (confirm timeout)",
                len(tasks), len(confirm_tasks),
            )


async def _check_expired_intents() -> None:
    """Expire intents that have exceeded their TTL."""
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(Intent).where(
                Intent.status.in_(["active", "matched"]),
                Intent.expires_at <= now,
            )
        )
        intents = result.scalars().all()
        for intent in intents:
            intent.status = "expired"
            logger.info("Intent %s expired", intent.id)

        if intents:
            await db.commit()
            logger.info("Expired %d intents", len(intents))


async def _check_expired_introductions() -> None:
    """Expire introductions that have exceeded their TTL (72h)."""
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(Introduction).where(
                Introduction.status.in_(["pending", "a_accepted", "b_accepted"]),
                Introduction.expires_at <= now,
            )
        )
        intros = result.scalars().all()
        for intro in intros:
            intro.status = "expired"
            logger.info("Introduction %s expired", intro.id)

        if intros:
            await db.commit()
            logger.info("Expired %d introductions", len(intros))
