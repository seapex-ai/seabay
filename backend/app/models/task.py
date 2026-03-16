from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    from_agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    to_agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    intent_id: Mapped[Optional[str]] = mapped_column(String(32))

    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    payload_ref: Mapped[Optional[str]] = mapped_column(String(500))
    payload_inline: Mapped[Optional[Dict]] = mapped_column(JSONB)

    risk_level: Mapped[str] = mapped_column(String(4), nullable=False, default="R0")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_delivery")

    requires_human_confirm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_confirmed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    human_confirm_timeout_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, default=3600,
    )
    human_confirm_channel: Mapped[Optional[str]] = mapped_column(String(20))
    human_confirm_token: Mapped[Optional[str]] = mapped_column(String(128))
    human_confirm_deadline: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    delivery_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_delivery_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=4,
    )
    next_delivery_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=259200)
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    extra_metadata: Mapped[Dict] = mapped_column("metadata", JSONB, default=dict)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )
    completed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))


class HumanConfirmSession(Base):
    __tablename__ = "human_confirm_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_for_agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    confirmed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
