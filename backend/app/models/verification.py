from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)

    method: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")

    identifier: Mapped[Optional[str]] = mapped_column(String(256))
    verification_code: Mapped[Optional[str]] = mapped_column(String(64))
    code_expires_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    extra_metadata: Mapped[Dict] = mapped_column("metadata", JSONB, default=dict)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )
