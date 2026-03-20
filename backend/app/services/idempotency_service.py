"""Idempotency service — request deduplication within a 24h window.

Prevents duplicate task creation and other mutating operations
when clients retry with the same idempotency key.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import IdempotencyConflictError
from app.core.id_generator import generate_id
from app.models.metrics import IdempotencyRecord

logger = logging.getLogger(__name__)


async def check_idempotency(
    db: AsyncSession,
    idempotency_key: str,
    agent_id: str,
) -> Optional[IdempotencyRecord]:
    """Check if an idempotency key has been used within the window.

    Returns the existing record if found (duplicate), None if new.
    """
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == idempotency_key,
            IdempotencyRecord.agent_id == agent_id,
            IdempotencyRecord.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def record_idempotency(
    db: AsyncSession,
    idempotency_key: str,
    agent_id: str,
    request_path: str,
    request_method: str,
    response_status: int,
    response_body: Any = None,
) -> IdempotencyRecord:
    """Record a successful idempotent request for deduplication."""
    body_hash = None
    if response_body is not None:
        body_str = json.dumps(response_body, sort_keys=True, default=str)
        body_hash = hashlib.sha256(body_str.encode()).hexdigest()

    now = datetime.now(timezone.utc)
    window_hours = settings.IDEMPOTENCY_WINDOW_HOURS

    record = IdempotencyRecord(
        id=generate_id("idmp"),
        idempotency_key=idempotency_key,
        agent_id=agent_id,
        request_path=request_path,
        request_method=request_method,
        response_status=response_status,
        response_body_hash=body_hash,
        expires_at=now + timedelta(hours=window_hours),
    )
    db.add(record)
    await db.flush()
    return record


async def ensure_not_duplicate(
    db: AsyncSession,
    idempotency_key: str,
    agent_id: str,
) -> None:
    """Raise IdempotencyConflictError if key was already used.

    Call this before processing a mutating request.
    """
    existing = await check_idempotency(db, idempotency_key, agent_id)
    if existing:
        raise IdempotencyConflictError(
            f"Request with idempotency key already processed "
            f"(original: {existing.request_method} {existing.request_path}, "
            f"status: {existing.response_status})"
        )
