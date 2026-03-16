"""Daily metrics models — trust & popularity snapshots (spec §14).

These tables store daily computed snapshots of trust and popularity signals,
enabling trend analysis without re-computing from raw data.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class TrustMetricsDaily(Base):
    __tablename__ = "trust_metrics_daily"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    date: Mapped[str] = mapped_column(Date, nullable=False)

    # Trust signals snapshot
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verification_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate_7d: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    report_rate_30d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    human_confirm_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    cancel_expire_rate_30d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Interaction counts
    total_interactions_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_interactions_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_count_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class PopularityMetricsDaily(Base):
    __tablename__ = "popularity_metrics_daily"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    date: Mapped[str] = mapped_column(Date, nullable=False)

    # Popularity signals snapshot
    task_received_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_received_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profile_views_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    search_appearances_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class PassportLiteReceipt(Base):
    """Trust portability receipt — allows agents to carry trust across platforms."""
    __tablename__ = "passport_lite_receipts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    receipt_type: Mapped[str] = mapped_column(String(30), nullable=False)
    issuer: Mapped[str] = mapped_column(String(100), nullable=False, default="seabay")
    subject_display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    trust_score_at_issue: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verification_level_at_issue: Mapped[str] = mapped_column(
        String(30), nullable=False, default="none",
    )
    interaction_count_at_issue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    issued_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    signature: Mapped[Optional[str]] = mapped_column(String(512))
    signature_alg: Mapped[str] = mapped_column(String(20), nullable=False, default="hmac-sha256")

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class IdempotencyRecord(Base):
    """Request deduplication within a 24h window."""
    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)

    request_path: Mapped[str] = mapped_column(String(255), nullable=False)
    request_method: Mapped[str] = mapped_column(String(10), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body_hash: Mapped[Optional[str]] = mapped_column(String(64))

    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
