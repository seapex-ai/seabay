"""Task lifecycle — endpoints with full state machine + negotiation messages.

Refactored to use task_service for all business logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.core.exceptions import NotFoundError
from app.core.middleware import trace_id_var
from app.database import get_db
from app.models.agent import Agent
from app.models.enums import TaskStatus
from app.models.task import Task
from app.schemas.task import (
    TaskCancelRequest,
    TaskCompleteRequest,
    TaskCreateRequest,
    TaskDeclineRequest,
    TaskHumanConfirmRequest,
    TaskResponse,
)
from app.services import budget_service, task_service

router = APIRouter()


@router.post("", status_code=201)
async def create_task(
    req: TaskCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """POST /v1/tasks — Create Task directly."""
    # Budget enforcement (spec §15.1)
    await budget_service.check_budget(db, current_agent, "new_direct_task")

    task = await task_service.create_task(
        db,
        from_agent=current_agent,
        to_agent_id=req.to_agent_id,
        task_type=req.task_type.value,
        description=req.description,
        payload_ref=req.payload_ref,
        payload_inline=req.payload_inline,
        risk_level=req.risk_level,
        ttl_seconds=req.ttl_seconds,
        idempotency_key=req.idempotency_key,
    )

    # Increment budget counter
    await budget_service.increment_budget(db, current_agent, "new_direct_task")

    return _task_to_response(task)


@router.get("/inbox", name="task_inbox")
async def get_inbox(
    status: str | None = None,
    task_type: str | None = None,
    risk_level: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/tasks/inbox — List inbox (cursor pagination)."""
    stmt = select(Task).where(Task.to_agent_id == current_agent.id)

    if status:
        stmt = stmt.where(Task.status == status)
    else:
        stmt = stmt.where(
            Task.status.in_([
                TaskStatus.PENDING_DELIVERY.value,
                TaskStatus.DELIVERED.value,
                TaskStatus.PENDING_ACCEPT.value,
            ])
        )

    if task_type:
        stmt = stmt.where(Task.task_type == task_type)
    if risk_level:
        stmt = stmt.where(Task.risk_level == risk_level)

    if cursor:
        stmt = stmt.where(Task.id > cursor)

    stmt = stmt.order_by(Task.created_at.desc()).limit(limit + 1)
    result = await db.execute(stmt)
    tasks = list(result.scalars().all())

    has_more = len(tasks) > limit
    if has_more:
        tasks = tasks[:limit]

    return {
        "data": [_task_to_response(t) for t in tasks],
        "next_cursor": tasks[-1].id if has_more else None,
        "has_more": has_more,
    }


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """GET /v1/tasks/{id} — Get Task details."""
    task = await task_service.get_task(db, task_id)
    if task.from_agent_id != current_agent.id and task.to_agent_id != current_agent.id:
        raise NotFoundError("Task")
    return _task_to_response(task)


@router.post("/{task_id}/accept")
async def accept_task(
    task_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """POST /v1/tasks/{id}/accept — Accept Task."""
    task = await task_service.get_task(db, task_id)
    task = await task_service.accept_task(db, task, current_agent)
    return _task_to_response(task)


@router.post("/{task_id}/decline")
async def decline_task(
    task_id: str,
    req: TaskDeclineRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """POST /v1/tasks/{id}/decline — Decline Task."""
    task = await task_service.get_task(db, task_id)
    task = await task_service.decline_task(db, task, current_agent)
    return _task_to_response(task)


@router.post("/{task_id}/confirm-human")
async def confirm_human(
    task_id: str,
    req: TaskHumanConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/tasks/{id}/confirm-human — Confirm high-risk action.

    Uses approval token, NOT agent API key.
    """
    task = await task_service.get_task(db, task_id)
    task = await task_service.confirm_human(db, task, req.token, req.confirmed)
    return _task_to_response(task)


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    req: TaskCompleteRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """POST /v1/tasks/{id}/complete — Mark Task complete."""
    task = await task_service.get_task(db, task_id)
    task = await task_service.complete_task(db, task, agent=current_agent, rating=req.rating)
    return _task_to_response(task)


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    req: TaskCancelRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """POST /v1/tasks/{id}/cancel — Cancel Task."""
    task = await task_service.get_task(db, task_id)
    task = await task_service.cancel_task(db, task, current_agent)
    return _task_to_response(task)


# ── Helpers ──

def _task_to_response(task: Task) -> TaskResponse:
    approval_url = None
    if task.status == TaskStatus.WAITING_HUMAN_CONFIRM.value and task.human_confirm_token:
        approval_url = f"https://seabay.ai/approve/?token={task.human_confirm_token}"

    # Card-ready envelope: ui_hint and next_actions depend on current status
    status = task.status
    ui_hint = _status_ui_hint(status)
    next_actions = _status_next_actions(status)

    return TaskResponse(
        id=task.id,
        from_agent_id=task.from_agent_id,
        to_agent_id=task.to_agent_id,
        intent_id=task.intent_id,
        task_type=task.task_type,
        description=task.description,
        risk_level=task.risk_level,
        status=status,
        requires_human_confirm=task.requires_human_confirm,
        human_confirm_channel=task.human_confirm_channel,
        human_confirm_deadline=task.human_confirm_deadline,
        approval_url=approval_url,
        delivery_attempts=task.delivery_attempts,
        expires_at=task.expires_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        cancelled_at=task.cancelled_at,
        trace_id=trace_id_var.get() or f"trc_{task.id[4:]}",
        ui_hint=ui_hint,
        next_actions=next_actions,
        data={"payload_ref": task.payload_ref} if task.payload_ref else None,
    )


def _status_ui_hint(status: str) -> str:
    return {
        "pending_delivery": "waiting",
        "delivered": "waiting",
        "pending_accept": "action_required",
        "accepted": "in_progress",
        "in_progress": "in_progress",
        "waiting_human_confirm": "approval_required",
        "completed": "success",
        "declined": "declined",
        "failed": "error",
        "cancelled": "cancelled",
        "expired": "expired",
    }.get(status, "unknown")


def _status_next_actions(status: str) -> list[str]:
    return {
        "pending_accept": ["accept", "decline"],
        "accepted": ["complete", "cancel"],
        "in_progress": ["complete", "cancel"],
        "waiting_human_confirm": ["confirm", "cancel"],
        "delivered": [],
        "completed": [],
    }.get(status, [])


# ── Task Messages (Phase B negotiation) ──


class _MessageBody(BaseModel):
    content: str = Field(max_length=2000)
    message_type: str = "text"
    structured_data: dict | None = None


class _MessageResponse(BaseModel):
    id: str
    task_id: str
    from_agent_id: str
    message_type: str
    content: str
    structured_data: dict | None
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/{task_id}/messages", status_code=201, name="send_task_message")
async def send_task_message(
    task_id: str,
    body: _MessageBody,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    from app.services import task_message_service
    msg = await task_message_service.send_message(
        db, task_id, current_agent.id,
        content=body.content,
        message_type=body.message_type,
        structured_data=body.structured_data,
    )
    await db.commit()
    return _MessageResponse.model_validate(msg)


@router.get("/{task_id}/messages", name="list_task_messages")
async def list_task_messages(
    task_id: str,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    from app.services import task_message_service
    messages = await task_message_service.list_messages(
        db, task_id, current_agent.id, limit=limit, cursor=cursor,
    )
    return {"data": [_MessageResponse.model_validate(m) for m in messages]}
