from __future__ import annotations

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class RateLimitBudget(Base):
    """Anti-spam budget tracking per agent per budget_type per window (§3.1)."""

    __tablename__ = "rate_limit_budgets"

    agent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    budget_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    window_start: Mapped[str] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_allowed: Mapped[int] = mapped_column(Integer, nullable=False)
