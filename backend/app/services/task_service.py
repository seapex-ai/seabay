"""Task service — lifecycle management, state machine, delivery, side effects.

Covers spec §12 (task state machine), §12.3 (risk levels & human confirm),
§12.4 (idempotency & delivery retry), §16 (deduplication).
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

# Maximum payload_inline size: 64KB when serialized to JSON
MAX_PAYLOAD_INLINE_BYTES = 64 * 1024

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    ConflictError,
    DLPBlockedError,
    InvalidRequestError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.dlp_scan_log import DLPScanLog
from app.models.enums import (
    HIGH_RISK_KEYWORDS,
    TASK_TRANSITIONS,
    RiskLevel,
    TaskStatus,
    requires_human_confirm,
)
from app.models.interaction import Interaction
from app.models.task import HumanConfirmSession, Task
from app.services.dlp_service import BLOCKED_PATTERNS, scan_content


async def get_task(db: AsyncSession, task_id: str) -> Task:
    """Get task by ID or raise NotFoundError."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task")
    return task


def validate_transition(task: Task, target: TaskStatus) -> None:
    """Validate state transition per spec §12.1."""
    current = TaskStatus(task.status)
    allowed = TASK_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise InvalidStateTransitionError(current.value, target.value)


def detect_risk_level(description: str, base_risk: RiskLevel = RiskLevel.R0) -> RiskLevel:
    """Auto-detect risk level from description keywords (spec §12.3)."""
    risk = base_risk
    desc_lower = (description or "").lower()
    for keyword, level in HIGH_RISK_KEYWORDS.items():
        if keyword in desc_lower:
            if level.value > risk.value:
                risk = level
    return risk


async def check_idempotency(
    db: AsyncSession,
    idempotency_key: Optional[str],
) -> Optional[Task]:
    """Check 24h deduplication window (spec §16).

    Returns existing task if duplicate, None if new.
    """
    if not idempotency_key:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.IDEMPOTENCY_WINDOW_HOURS)
    result = await db.execute(
        select(Task).where(
            Task.idempotency_key == idempotency_key,
            Task.created_at > cutoff,
        )
    )
    return result.scalar_one_or_none()


async def run_dlp_scan(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    text: str,
) -> list[dict]:
    """Run DLP scan and log findings. Raises DLPBlockedError if blocked."""
    findings = scan_content(text)
    for finding in findings:
        db.add(DLPScanLog(
            id=generate_id("dlp_scan_log"),
            entity_type=entity_type,
            entity_id=entity_id,
            pattern_matched=finding["pattern"],
            action_taken=finding["action"],
        ))
        if finding["pattern"] in BLOCKED_PATTERNS:
            await db.flush()
            raise DLPBlockedError(pattern=finding["pattern"])
    return findings


async def create_task(
    db: AsyncSession,
    from_agent: Agent,
    to_agent_id: str,
    task_type: str,
    description: Optional[str] = None,
    payload_ref: Optional[str] = None,
    payload_inline: Optional[dict] = None,
    risk_level: RiskLevel = RiskLevel.R0,
    ttl_seconds: int = 259200,
    idempotency_key: Optional[str] = None,
    intent_id: Optional[str] = None,
) -> Task:
    """Create a new task with all validations.

    Steps:
    1. Idempotency check
    2. Target exists check
    3. Contact policy enforcement
    4. DLP scan
    5. Risk level auto-detection
    6. Create task
    """
    from app.services import relationship_service

    if to_agent_id == from_agent.id:
        raise InvalidRequestError("Cannot create task to self")

    # Validate payload_inline size (64KB limit)
    if payload_inline is not None:
        payload_bytes = len(json.dumps(payload_inline, default=str).encode("utf-8"))
        if payload_bytes > MAX_PAYLOAD_INLINE_BYTES:
            raise InvalidRequestError(
                f"payload_inline exceeds 64KB limit ({payload_bytes} bytes)"
            )

    # Check target exists
    target_result = await db.execute(select(Agent).where(Agent.id == to_agent_id))
    target = target_result.scalar_one_or_none()
    if not target:
        raise NotFoundError("Target agent")
    if target.status in ("suspended", "banned"):
        raise InvalidRequestError(f"Target agent is {target.status}")

    # Idempotency check
    idemp_key = idempotency_key or str(uuid.uuid4())
    existing = await check_idempotency(db, idemp_key)
    if existing:
        raise ConflictError(message="Duplicate task (idempotency_key already used within 24h)")

    # Contact policy
    await relationship_service.check_contact_allowed(db, from_agent, target)

    # Budget check (anti-spam, spec §15.1)
    from app.services import budget_service
    await budget_service.check_budget(db, from_agent, "new_direct_task")

    # DLP scan
    task_id = generate_id("task")
    scan_text = description or ""
    if scan_text:
        await run_dlp_scan(db, "task", task_id, scan_text)

    # Auto-detect risk
    risk = detect_risk_level(scan_text, risk_level)
    needs_confirm = requires_human_confirm(risk)

    now = datetime.now(timezone.utc)
    task = Task(
        id=task_id,
        idempotency_key=idemp_key,
        from_agent_id=from_agent.id,
        to_agent_id=to_agent_id,
        intent_id=intent_id,
        task_type=task_type,
        description=description,
        payload_ref=payload_ref,
        payload_inline=payload_inline,
        risk_level=risk.value,
        status=TaskStatus.PENDING_DELIVERY.value,
        requires_human_confirm=needs_confirm,
        ttl_seconds=ttl_seconds,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


async def accept_task(
    db: AsyncSession,
    task: Task,
    agent: Agent,
) -> Task:
    """Accept a task. If R2/R3, auto-transition to waiting_human_confirm."""
    if task.to_agent_id != agent.id:
        raise InvalidRequestError("Only target agent can accept")

    # Handle full chain: pending_delivery → delivered → pending_accept → accepted
    if task.status == TaskStatus.PENDING_DELIVERY.value:
        validate_transition(task, TaskStatus.DELIVERED)
        task.status = TaskStatus.DELIVERED.value
        task.delivery_attempts = (task.delivery_attempts or 0) + 1
        await db.flush()

    if task.status == TaskStatus.DELIVERED.value:
        validate_transition(task, TaskStatus.PENDING_ACCEPT)
        task.status = TaskStatus.PENDING_ACCEPT.value
        await db.flush()

    validate_transition(task, TaskStatus.ACCEPTED)
    task.status = TaskStatus.ACCEPTED.value
    await db.flush()

    # Auto-transition to in_progress
    task.status = TaskStatus.IN_PROGRESS.value

    # If requires human confirm, create session
    if task.requires_human_confirm:
        timeout = (
            settings.TASK_HUMAN_CONFIRM_TIMEOUT_R3
            if task.risk_level == "R3"
            else settings.TASK_HUMAN_CONFIRM_TIMEOUT_R2
        )
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(48)

        task.status = TaskStatus.WAITING_HUMAN_CONFIRM.value
        task.human_confirm_channel = "hosted_web"
        task.human_confirm_token = token
        task.human_confirm_deadline = now + timedelta(seconds=timeout)

        db.add(HumanConfirmSession(
            id=generate_id("human_confirm_session"),
            task_id=task.id,
            issued_for_agent_id=task.from_agent_id,
            token=token,
            channel="hosted_web",
            expires_at=now + timedelta(seconds=timeout),
        ))

    await db.flush()
    await db.refresh(task)
    return task


async def decline_task(
    db: AsyncSession,
    task: Task,
    agent: Agent,
) -> Task:
    """Decline a task."""
    if task.to_agent_id != agent.id:
        raise InvalidRequestError("Only target agent can decline")

    # Auto-advance to pending_accept so decline is valid
    if task.status == TaskStatus.PENDING_DELIVERY.value:
        task.status = TaskStatus.DELIVERED.value
        task.delivery_attempts = (task.delivery_attempts or 0) + 1
        await db.flush()
    if task.status == TaskStatus.DELIVERED.value:
        task.status = TaskStatus.PENDING_ACCEPT.value
        await db.flush()

    validate_transition(task, TaskStatus.DECLINED)
    task.status = TaskStatus.DECLINED.value

    db.add(Interaction(
        id=generate_id("interaction"),
        task_id=task.id,
        from_agent_id=task.from_agent_id,
        to_agent_id=task.to_agent_id,
        outcome="declined",
    ))

    await db.flush()
    await db.refresh(task)
    return task


async def complete_task(
    db: AsyncSession,
    task: Task,
    agent: Agent,
    rating: Optional[float] = None,
) -> Task:
    """Complete a task (R0/R1 only via API key; R2/R3 via confirm-human)."""
    from app.services import relationship_service

    # Only the task sender or receiver can complete
    if task.from_agent_id != agent.id and task.to_agent_id != agent.id:
        raise InvalidRequestError("Only task sender or receiver can complete")

    if task.requires_human_confirm:
        raise InvalidRequestError("R2/R3 tasks must be completed via human confirmation")

    validate_transition(task, TaskStatus.COMPLETED)
    now = datetime.now(timezone.utc)
    task.status = TaskStatus.COMPLETED.value
    task.completed_at = now

    # Compute latency_ms from task creation to completion
    latency_ms = None
    if task.created_at:
        created = task.created_at
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        latency_ms = int((now - created).total_seconds() * 1000)

    # Log interaction
    interaction = Interaction(
        id=generate_id("interaction"),
        task_id=task.id,
        from_agent_id=task.from_agent_id,
        to_agent_id=task.to_agent_id,
        outcome="success",
        rating_by_from=int(rating) if rating else None,
        latency_ms=latency_ms,
    )
    db.add(interaction)

    # Update relationship stats
    await relationship_service.record_interaction_on_edge(
        db, task.from_agent_id, task.to_agent_id,
        success=True, rating=int(rating) if rating else None,
    )

    # Auto-add 'collaborated' origin
    await relationship_service.add_collaborated_origin(
        db, task.from_agent_id, task.to_agent_id, task.id,
    )

    # Re-derive strength
    await relationship_service.update_strength(db, task.from_agent_id, task.to_agent_id)
    await relationship_service.update_strength(db, task.to_agent_id, task.from_agent_id)

    await db.flush()
    await db.refresh(task)
    return task


async def confirm_human(
    db: AsyncSession,
    task: Task,
    token: str,
    confirmed: bool,
) -> Task:
    """Process human confirmation for R2/R3 tasks."""
    from app.services import relationship_service

    if task.status != TaskStatus.WAITING_HUMAN_CONFIRM.value:
        raise InvalidRequestError("Task is not waiting for human confirmation")

    # Verify token
    session_result = await db.execute(
        select(HumanConfirmSession).where(
            HumanConfirmSession.task_id == task.id,
            HumanConfirmSession.token == token,
            HumanConfirmSession.status == "pending",
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise InvalidRequestError("Invalid or expired confirmation token")

    now = datetime.now(timezone.utc)
    if session.expires_at and now > session.expires_at:
        session.status = "expired"
        task.status = TaskStatus.EXPIRED.value
        await db.flush()
        raise InvalidRequestError("Confirmation has expired")

    if confirmed:
        session.status = "confirmed"
        session.confirmed_at = now
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = now
        task.human_confirmed_at = now

        db.add(Interaction(
            id=generate_id("interaction"),
            task_id=task.id,
            from_agent_id=task.from_agent_id,
            to_agent_id=task.to_agent_id,
            outcome="success",
        ))

        await relationship_service.add_collaborated_origin(
            db, task.from_agent_id, task.to_agent_id, task.id,
        )
        await relationship_service.record_interaction_on_edge(
            db, task.from_agent_id, task.to_agent_id, success=True,
        )
    else:
        session.status = "rejected"
        task.status = TaskStatus.CANCELLED.value
        task.cancelled_at = now

        db.add(Interaction(
            id=generate_id("interaction"),
            task_id=task.id,
            from_agent_id=task.from_agent_id,
            to_agent_id=task.to_agent_id,
            outcome="cancelled",
        ))

    await db.flush()
    await db.refresh(task)
    return task


async def cancel_task(
    db: AsyncSession,
    task: Task,
    agent: Agent,
) -> Task:
    """Cancel a task (only sender can cancel)."""
    if task.from_agent_id != agent.id:
        raise InvalidRequestError("Only sender can cancel")

    validate_transition(task, TaskStatus.CANCELLED)
    task.status = TaskStatus.CANCELLED.value
    task.cancelled_at = datetime.now(timezone.utc)

    db.add(Interaction(
        id=generate_id("interaction"),
        task_id=task.id,
        from_agent_id=task.from_agent_id,
        to_agent_id=task.to_agent_id,
        outcome="cancelled",
    ))

    await db.flush()
    await db.refresh(task)
    return task


def task_to_response(task: Task) -> dict:
    """Convert Task to response dict with approval_url for R2/R3."""
    approval_url = None
    if task.status == TaskStatus.WAITING_HUMAN_CONFIRM.value and task.human_confirm_token:
        approval_url = f"https://seabay.ai/approve/{task.human_confirm_token}"

    return {
        "id": task.id,
        "from_agent_id": task.from_agent_id,
        "to_agent_id": task.to_agent_id,
        "intent_id": task.intent_id,
        "task_type": task.task_type,
        "description": task.description,
        "risk_level": task.risk_level,
        "status": task.status,
        "requires_human_confirm": task.requires_human_confirm,
        "human_confirm_channel": task.human_confirm_channel,
        "human_confirm_deadline": task.human_confirm_deadline,
        "approval_url": approval_url,
        "delivery_attempts": task.delivery_attempts,
        "expires_at": task.expires_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
        "cancelled_at": task.cancelled_at,
    }
