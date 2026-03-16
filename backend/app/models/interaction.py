from __future__ import annotations

from typing import Optional

from sqlalchemy import DateTime, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False)
    from_agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    to_agent_id: Mapped[str] = mapped_column(String(32), nullable=False)

    intent: Mapped[Optional[str]] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    rating_by_from: Mapped[Optional[int]] = mapped_column(SmallInteger)
    rating_by_to: Mapped[Optional[int]] = mapped_column(SmallInteger)
    report_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
