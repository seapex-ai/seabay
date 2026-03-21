"""Audit log model — persistent moderation audit trail (V1.6).

Replaces the in-memory audit log from V1.5.
Stores all moderation actions, admin actions, and auto-moderation events.
"""

from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(32))
    target_id: Mapped[Optional[str]] = mapped_column(String(32))
    details: Mapped[Dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
