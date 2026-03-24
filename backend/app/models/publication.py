from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)

    publication_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[Dict] = mapped_column(JSONB, default=dict)

    tags: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    price_summary: Mapped[Optional[str]] = mapped_column(String(128))
    availability_summary: Mapped[Optional[str]] = mapped_column(String(128))
    location_city: Mapped[Optional[str]] = mapped_column(String(100))
    location_country: Mapped[Optional[str]] = mapped_column(String(2))

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    visibility_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    expires_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )
