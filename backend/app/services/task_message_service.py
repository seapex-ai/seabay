"""Task message service — lightweight task-scoped negotiation.

Not a full chat — limited to structured request/reply within a task context.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.id_generator import generate_id
from app.models.task import Task
from app.models.task_message import TaskMessage

logger = logging.getLogger(__name__)

MAX_MESSAGES_PER_TASK = 50


async def send_message(
    db: AsyncSession,
    task_id: str,
    from_agent_id: str,
    *,
    content: str,
    message_type: str = "text",
    structured_data: dict | None = None,
) -> TaskMessage:
    # Verify task exists and agent is a participant
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task")
    if from_agent_id not in (task.from_agent_id, task.to_agent_id):
        raise ForbiddenError("Not a participant of this task")

    # Check message limit
    count_result = await db.execute(
        select(TaskMessage).where(TaskMessage.task_id == task_id)
    )
    existing = list(count_result.scalars().all())
    if len(existing) >= MAX_MESSAGES_PER_TASK:
        raise ForbiddenError(f"Message limit ({MAX_MESSAGES_PER_TASK}) reached for this task")

    msg = TaskMessage(
        id=generate_id("msg"),
        task_id=task_id,
        from_agent_id=from_agent_id,
        message_type=message_type,
        content=content,
        structured_data=structured_data,
    )
    db.add(msg)
    await db.flush()

    # Update task conversation_ref if not set
    if not task.conversation_ref:
        task.conversation_ref = f"thread:{task_id}"
        await db.flush()

    logger.info("Message %s sent in task %s by %s", msg.id, task_id, from_agent_id)
    return msg


async def list_messages(
    db: AsyncSession,
    task_id: str,
    agent_id: str,
    limit: int = 50,
    cursor: str | None = None,
) -> list[TaskMessage]:
    # Verify task exists and agent is participant
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task")
    if agent_id not in (task.from_agent_id, task.to_agent_id):
        raise ForbiddenError("Not a participant of this task")

    stmt = select(TaskMessage).where(TaskMessage.task_id == task_id)
    if cursor:
        stmt = stmt.where(TaskMessage.id > cursor)
    stmt = stmt.order_by(TaskMessage.created_at.asc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
