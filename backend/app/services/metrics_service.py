"""Metrics service — daily trust & popularity metric aggregation.

Open-Core: Reference implementation for metric snapshots and rollups.
Production deployments may override storage and aggregation via app.hosted.

Computes and stores daily snapshots of trust and popularity signals
for trend analysis and dashboard rendering (spec §14).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.metrics import (
    PassportLiteReceipt,
    PopularityMetricsDaily,
    TrustMetricsDaily,
)
from app.services import trust_service

logger = logging.getLogger(__name__)


async def compute_daily_trust_metrics(
    db: AsyncSession,
    agent_id: str,
    target_date: Optional[date] = None,
) -> TrustMetricsDaily:
    """Compute and store daily trust metrics for one agent."""
    target_date = target_date or date.today()

    # Check if already computed for this date
    existing = await db.execute(
        select(TrustMetricsDaily).where(
            TrustMetricsDaily.agent_id == agent_id,
            TrustMetricsDaily.date == target_date,
        )
    )
    record = existing.scalar_one_or_none()

    # Compute signals
    signals = await trust_service.compute_trust_signals(db, agent_id)
    score = trust_service.compute_trust_score(signals)

    if record:
        # Update existing record
        record.trust_score = score
        record.verification_weight = signals.get("verification_weight", 0)
        record.success_rate_7d = signals.get("success_rate_7d", 1.0)
        record.report_rate_30d = signals.get("report_rate_30d", 0.0)
        record.human_confirm_success_rate = signals.get("human_confirm_success_rate", 1.0)
        record.cancel_expire_rate_30d = signals.get("cancel_expire_rate_30d", 0.0)
        record.avg_latency_ms = signals.get("avg_latency_ms", 0.0)
        record.total_interactions_7d = signals.get("total_interactions_7d", 0)
        record.total_interactions_30d = signals.get("total_interactions_30d", 0)
        record.report_count_30d = signals.get("report_count_30d", 0)
    else:
        record = TrustMetricsDaily(
            id=generate_id("trust_metric"),
            agent_id=agent_id,
            date=target_date,
            trust_score=score,
            verification_weight=signals.get("verification_weight", 0),
            success_rate_7d=signals.get("success_rate_7d", 1.0),
            report_rate_30d=signals.get("report_rate_30d", 0.0),
            human_confirm_success_rate=signals.get("human_confirm_success_rate", 1.0),
            cancel_expire_rate_30d=signals.get("cancel_expire_rate_30d", 0.0),
            avg_latency_ms=signals.get("avg_latency_ms", 0.0),
            total_interactions_7d=signals.get("total_interactions_7d", 0),
            total_interactions_30d=signals.get("total_interactions_30d", 0),
            report_count_30d=signals.get("report_count_30d", 0),
        )
        db.add(record)

    await db.flush()
    return record


async def compute_daily_popularity_metrics(
    db: AsyncSession,
    agent_id: str,
    target_date: Optional[date] = None,
) -> PopularityMetricsDaily:
    """Compute and store daily popularity metrics for one agent."""
    target_date = target_date or date.today()

    # Check if already computed
    existing = await db.execute(
        select(PopularityMetricsDaily).where(
            PopularityMetricsDaily.agent_id == agent_id,
            PopularityMetricsDaily.date == target_date,
        )
    )
    record = existing.scalar_one_or_none()

    signals = await trust_service.compute_popularity_signals(db, agent_id)

    if record:
        record.task_received_count = signals.get("task_received_count", 0)
        record.task_received_7d = signals.get("task_received_7d", 0)
        record.profile_views_7d = signals.get("profile_views_7d", 0)
        record.search_appearances_7d = signals.get("search_appearances_7d", 0)
    else:
        record = PopularityMetricsDaily(
            id=generate_id("pop_metric"),
            agent_id=agent_id,
            date=target_date,
            task_received_count=signals.get("task_received_count", 0),
            task_received_7d=signals.get("task_received_7d", 0),
            profile_views_7d=signals.get("profile_views_7d", 0),
            search_appearances_7d=signals.get("search_appearances_7d", 0),
        )
        db.add(record)

    await db.flush()
    return record


async def aggregate_all_metrics(db: AsyncSession) -> int:
    """Compute daily metrics for all active agents. Returns count processed."""
    result = await db.execute(
        select(Agent.id).where(
            Agent.status.notin_(["suspended", "banned"]),
        )
    )
    agent_ids = [row[0] for row in result.all()]

    count = 0
    for agent_id in agent_ids:
        try:
            await compute_daily_trust_metrics(db, agent_id)
            await compute_daily_popularity_metrics(db, agent_id)
            count += 1
        except Exception:
            logger.exception("Failed to compute metrics for agent %s", agent_id)

    return count


async def get_trust_trend(
    db: AsyncSession,
    agent_id: str,
    days: int = 30,
) -> list[dict]:
    """Get trust score trend for the last N days."""
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(TrustMetricsDaily).where(
            TrustMetricsDaily.agent_id == agent_id,
            TrustMetricsDaily.date >= cutoff,
        ).order_by(TrustMetricsDaily.date.asc())
    )
    records = result.scalars().all()
    return [
        {
            "date": str(r.date),
            "trust_score": r.trust_score,
            "success_rate_7d": r.success_rate_7d,
            "report_count_30d": r.report_count_30d,
        }
        for r in records
    ]


async def issue_passport_receipt(
    db: AsyncSession,
    agent_id: str,
    receipt_type: str = "trust_snapshot",
) -> PassportLiteReceipt:
    """Issue a Passport Lite receipt for trust portability."""
    signals = await trust_service.compute_trust_signals(db, agent_id)
    score = trust_service.compute_trust_score(signals)

    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Agent")

    now = datetime.now(timezone.utc)
    receipt = PassportLiteReceipt(
        id=generate_id("receipt"),
        agent_id=agent_id,
        receipt_type=receipt_type,
        issuer="seabay",
        subject_display_name=agent.display_name,
        trust_score_at_issue=score,
        verification_level_at_issue=agent.verification_level,
        interaction_count_at_issue=signals.get("total_interactions_30d", 0),
        issued_at=now,
        expires_at=now + timedelta(days=90),
    )
    db.add(receipt)
    await db.flush()
    return receipt


async def get_passport_receipts(
    db: AsyncSession,
    agent_id: str,
) -> list[PassportLiteReceipt]:
    """Get all valid passport receipts for an agent."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PassportLiteReceipt).where(
            PassportLiteReceipt.agent_id == agent_id,
            PassportLiteReceipt.revoked_at.is_(None),
            (PassportLiteReceipt.expires_at > now) | (PassportLiteReceipt.expires_at.is_(None)),
        ).order_by(PassportLiteReceipt.issued_at.desc())
    )
    return list(result.scalars().all())
