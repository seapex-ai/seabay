from __future__ import annotations

from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Introduction(Base):
    __tablename__ = "introductions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    introducer_id: Mapped[str] = mapped_column(
        "introducer_agent_id", String(32), nullable=False,
    )
    target_a_id: Mapped[str] = mapped_column(
        "target_a_agent_id", String(32), nullable=False,
    )
    target_b_id: Mapped[str] = mapped_column(
        "target_b_agent_id", String(32), nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column("message", Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    a_responded_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    b_responded_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=259200)

    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
