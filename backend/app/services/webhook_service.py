"""Webhook service — delivery with retry, HMAC signatures, timeout.

Covers spec §12.4 (delivery retry), webhook notification system.
Retry schedule: immediate, +1s, +5s, +25s (4 attempts total).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.enums import TaskStatus
from app.models.task import Task

logger = logging.getLogger(__name__)

# Retry delays in seconds: immediate, 1s, 5s, 25s
RETRY_DELAYS = [0, 1, 5, 25]
WEBHOOK_TIMEOUT = 10.0  # seconds


def sign_payload(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def deliver_webhook(
    endpoint: str,
    event: str,
    payload: dict,
    secret: Optional[str] = None,
    timeout: float = WEBHOOK_TIMEOUT,
) -> tuple[bool, int, Optional[str]]:
    """Deliver a single webhook request.

    Returns (success, status_code, error_message).
    """
    body = json.dumps({"event": event, **payload})
    headers = {
        "Content-Type": "application/json",
        "X-Seabay-Event": event,
    }
    if secret:
        headers["X-Seabay-Signature"] = f"sha256={sign_payload(body.encode(), secret)}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, content=body, headers=headers)
            if 200 <= response.status_code < 300:
                return True, response.status_code, None
            elif 400 <= response.status_code < 500:
                # Client error: not retryable
                return False, response.status_code, f"Client error: {response.status_code}"
            else:
                # Server error: retryable
                return False, response.status_code, f"Server error: {response.status_code}"
    except httpx.TimeoutException:
        return False, 0, "Timeout"
    except httpx.ConnectError:
        return False, 0, "Connection refused"
    except Exception as e:
        return False, 0, str(e)


async def deliver_task_to_agent(
    db: AsyncSession,
    task: Task,
) -> bool:
    """Deliver a task to the target agent's webhook endpoint.

    Implements retry logic per spec §12.4:
    - Attempt 1: immediate
    - Attempt 2: +1s delay
    - Attempt 3: +5s delay
    - Attempt 4: +25s delay
    - After 4 failures: status → failed

    For V1.5: single attempt per call; background worker handles retries.
    """
    # Get target agent
    result = await db.execute(select(Agent).where(Agent.id == task.to_agent_id))
    target = result.scalar_one_or_none()
    if not target:
        logger.warning("Task %s: target agent not found, marking as failed", task.id)
        task.status = TaskStatus.FAILED.value
        task.delivery_attempts += 1
        await db.flush()
        return False

    if not target.endpoint:
        # Polling-mode agent: no webhook endpoint, skip to pending_accept.
        # Agent will pick up the task via GET /tasks/inbox.
        task.status = TaskStatus.PENDING_ACCEPT.value
        task.delivery_attempts += 1
        logger.info("Task %s: target agent uses polling mode, marked as pending_accept", task.id)

        # Still push SSE notification (best-effort)
        from app.services import notification_service
        await notification_service.notify_task_event(
            agent_id=task.to_agent_id,
            event_type="task.created",
            task_id=task.id,
            from_agent_id=task.from_agent_id,
            task_type=task.task_type,
            status=task.status,
            description=task.description,
        )
        await db.flush()
        return True

    # Build webhook payload
    payload = {
        "task": {
            "id": task.id,
            "from_agent_id": task.from_agent_id,
            "task_type": task.task_type,
            "description": task.description,
            "risk_level": task.risk_level,
            "payload_inline": task.payload_inline,
            "requires_human_confirm": task.requires_human_confirm,
            "expires_at": str(task.expires_at) if task.expires_at else None,
            "created_at": str(task.created_at) if task.created_at else None,
        },
    }

    success, status_code, error = await deliver_webhook(
        endpoint=target.endpoint,
        event="task.created",
        payload=payload,
    )

    task.delivery_attempts += 1

    # Also push via SSE (best-effort)
    from app.services import notification_service
    await notification_service.notify_task_event(
        agent_id=task.to_agent_id,
        event_type="task.created",
        task_id=task.id,
        from_agent_id=task.from_agent_id,
        task_type=task.task_type,
        status=task.status,
        description=task.description,
    )

    if success:
        task.status = TaskStatus.DELIVERED.value
        logger.info("Task %s delivered successfully", task.id)
    else:
        logger.warning(
            "Task %s delivery attempt %d failed: %s",
            task.id, task.delivery_attempts, error,
        )
        if task.delivery_attempts >= task.max_delivery_attempts:
            task.status = TaskStatus.FAILED.value
            logger.error("Task %s delivery failed after %d attempts", task.id, task.delivery_attempts)
        else:
            # Schedule next retry
            delay = RETRY_DELAYS[min(task.delivery_attempts, len(RETRY_DELAYS) - 1)]
            task.next_delivery_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

    await db.flush()
    return success


async def notify_task_outcome(
    db: AsyncSession,
    task: Task,
    event: str,
) -> bool:
    """Notify the from_agent about task outcome (completed/declined/cancelled)."""
    result = await db.execute(select(Agent).where(Agent.id == task.from_agent_id))
    from_agent = result.scalar_one_or_none()
    if not from_agent or not from_agent.endpoint:
        return False

    payload = {
        "task": {
            "id": task.id,
            "status": task.status,
            "to_agent_id": task.to_agent_id,
            "completed_at": str(task.completed_at) if task.completed_at else None,
            "cancelled_at": str(task.cancelled_at) if task.cancelled_at else None,
        },
    }

    # Also push via SSE
    from app.services import notification_service
    await notification_service.notify_task_event(
        agent_id=task.from_agent_id,
        event_type=event,
        task_id=task.id,
        from_agent_id=task.to_agent_id,
        task_type=task.task_type,
        status=task.status,
    )

    success, _, error = await deliver_webhook(
        endpoint=from_agent.endpoint,
        event=event,
        payload=payload,
    )
    if not success:
        logger.warning("Failed to notify from_agent %s: %s", from_agent.id, error)
    return success


async def notify_introduction(
    db: AsyncSession,
    target_agent_id: str,
    introducer_display_name: str,
    other_agent_display_name: str,
    introduction_id: str,
) -> bool:
    """Notify a target agent about a new introduction."""
    result = await db.execute(select(Agent).where(Agent.id == target_agent_id))
    target = result.scalar_one_or_none()
    if not target or not target.endpoint:
        return False

    payload = {
        "introduction": {
            "id": introduction_id,
            "introducer": introducer_display_name,
            "other_agent": other_agent_display_name,
        },
    }

    # Also push via SSE
    from app.services import notification_service
    await notification_service.notify_introduction(
        agent_id=target_agent_id,
        introduction_id=introduction_id,
        introducer_id="",  # display name only at webhook level
        other_agent_id="",
        reason=None,
        status="pending",
    )

    success, _, _ = await deliver_webhook(
        endpoint=target.endpoint,
        event="introduction.created",
        payload=payload,
    )
    return success
