from __future__ import annotations

from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    reported_agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    reporter_agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(String(32))

    reason_code: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    reporter_verification_level: Mapped[Optional[str]] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
