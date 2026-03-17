from __future__ import annotations

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class DLPScanLog(Base):
    """Minimal DLP detection log (§3.2)."""

    __tablename__ = "dlp_scan_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern_matched: Mapped[str] = mapped_column(String(50), nullable=False)
    action_taken: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
