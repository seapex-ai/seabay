from __future__ import annotations

from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Organization(Base):
    """Organization entity for team/enterprise management."""
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    owner_agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    verification_level: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    domain: Mapped[Optional[str]] = mapped_column(String(200))

    default_contact_policy: Mapped[str] = mapped_column(String(30), nullable=False, default="known_direct")
    default_visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="network_only")
    allowed_agent_types: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)

    max_members: Mapped[int] = mapped_column(default=100)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )


class OrgMembership(Base):
    """Membership in an organization."""
    __tablename__ = "org_memberships"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class OrgPolicy(Base):
    """Organization-level policy rules."""
    __tablename__ = "org_policies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id"), nullable=False)

    policy_type: Mapped[str] = mapped_column(String(30), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_value: Mapped[str] = mapped_column(Text, nullable=False)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )
