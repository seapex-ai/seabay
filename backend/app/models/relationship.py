from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class RelationshipEdge(Base):
    __tablename__ = "relationship_edges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    from_agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    to_agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)

    strength: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_direct_task: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_introduce: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_blocked: Mapped[bool] = mapped_column("blocked", Boolean, nullable=False, default=False)
    blocked_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    last_rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    tags: Mapped[Optional[List]] = mapped_column(JSONB, default=list)

    interaction_count: Mapped[int] = mapped_column(
        "total_interactions", Integer, nullable=False, default=0,
    )
    success_count: Mapped[int] = mapped_column(
        "successful_interactions", Integer, nullable=False, default=0,
    )
    last_interaction_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )


class RelationshipOrigin(Base):
    __tablename__ = "relationship_origins"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    edge_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("relationship_edges.id", ondelete="CASCADE"), nullable=False,
    )
    origin_type: Mapped[str] = mapped_column(String(30), nullable=False)
    origin_status: Mapped[str] = mapped_column(
        "status", String(20), nullable=False, default="active",
    )
    source_id: Mapped[Optional[str]] = mapped_column(String(32))
    expired_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
