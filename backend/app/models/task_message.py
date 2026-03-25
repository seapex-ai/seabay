from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class TaskMessage(Base):
    """Lightweight task-scoped negotiation messages.

    Not a full chat system — limited to structured request/reply
    for price, time, availability negotiation within a task context.
    """
    __tablename__ = "task_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("tasks.id"), nullable=False)
    from_agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)

    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[Optional[Dict]] = mapped_column(JSONB)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
