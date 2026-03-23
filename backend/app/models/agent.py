from __future__ import annotations

from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False, default="personal")
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="individual")
    owner_id: Mapped[Optional[str]] = mapped_column(String(64))
    runtime: Mapped[Optional[str]] = mapped_column(String(50))
    framework: Mapped[Optional[str]] = mapped_column(String(50))
    endpoint: Mapped[Optional[str]] = mapped_column(String(500))
    namespace: Mapped[Optional[str]] = mapped_column(String(200))
    api_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_prefix: Mapped[Optional[str]] = mapped_column(String(16), index=True)

    verification_level: Mapped[str] = mapped_column(
        String(30), nullable=False, default="none",
    )
    public_key: Mapped[Optional[str]] = mapped_column(Text)
    signature_alg: Mapped[Optional[str]] = mapped_column(String(20))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="online")
    contact_policy: Mapped[str] = mapped_column(
        String(30), nullable=False, default="known_direct",
    )
    introduction_policy: Mapped[str] = mapped_column(
        String(30), nullable=False, default="confirm_required",
    )
    visibility_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="network_only",
    )

    last_seen_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    key_rotated_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    passport_display_name: Mapped[Optional[str]] = mapped_column(String(128))
    passport_tagline: Mapped[Optional[str]] = mapped_column(String(256))
    passport_avatar_url: Mapped[Optional[str]] = mapped_column(Text)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    profile: Mapped["Profile"] = relationship(
        back_populates="agent", uselist=False, cascade="all, delete-orphan",
    )
    field_visibilities: Mapped[List["ProfileFieldVisibility"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan",
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False, unique=True)

    bio: Mapped[Optional[str]] = mapped_column(Text)
    skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    risk_capabilities: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    interests: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    languages: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    location_city: Mapped[Optional[str]] = mapped_column(String(100))
    location_country: Mapped[Optional[str]] = mapped_column(String(2))
    timezone: Mapped[Optional[str]] = mapped_column(String(40))
    pricing: Mapped[Optional[str]] = mapped_column(String(50), default="free")
    profile_theme: Mapped[Optional[str]] = mapped_column(String(50))

    can_offer: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    looking_for: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    pricing_hint: Mapped[Optional[str]] = mapped_column(String(128))
    homepage_url: Mapped[Optional[str]] = mapped_column(Text)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    agent: Mapped["Agent"] = relationship(back_populates="profile")


class ProfileFieldVisibility(Base):
    __tablename__ = "profile_field_visibility"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="network_only")

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    agent: Mapped["Agent"] = relationship(back_populates="field_visibilities")
