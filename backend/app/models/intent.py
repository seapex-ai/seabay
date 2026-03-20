from __future__ import annotations

from typing import Dict

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    from_agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)

    category: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    structured_requirements: Mapped[Dict] = mapped_column(JSONB, default=dict)
    audience_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="public")

    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active")
    max_matches: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    ttl_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )
