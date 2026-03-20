from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Circle(Base):
    __tablename__ = "circles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)

    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="private")
    join_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="invite_only")
    contact_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="request_only")
    max_members: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    invite_link_token: Mapped[Optional[str]] = mapped_column(String(64))
    invite_link_ttl: Mapped[Optional[int]] = mapped_column(Integer, default=604800)  # 7 days in seconds

    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )


class CircleMembership(Base):
    __tablename__ = "circle_memberships"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    circle_id: Mapped[str] = mapped_column(String(32), ForeignKey("circles.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(8), nullable=False, default="member")
    invited_by: Mapped[Optional[str]] = mapped_column(String(32))

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    joined_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CircleJoinRequest(Base):
    __tablename__ = "circle_join_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    circle_id: Mapped[str] = mapped_column(String(32), ForeignKey("circles.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")

    reviewed_by: Mapped[Optional[str]] = mapped_column(String(32))
    reviewed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
