"""Trust & popularity service — signal aggregation, score calculation.

Open-Core: Reference implementation with default weights.
Production deployment may override weights via app.hosted.weights.

Covers spec §14 (trust ≠ popularity, separate tables/display/sorting).

Trust Input Signals (§14.2):
- verification_level: High weight
- success_rate_7d: High weight
- report_rate_30d: High weight (negative)
- human_confirm_success_rate: Medium weight
- avg_response_latency: Low weight
- cancel_expire_rate_30d: Medium weight (negative)

Popularity Signals (separate):
- profile_views
- search_appearances
- task_received_count
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.enums import VERIFICATION_WEIGHTS, VerificationLevel
from app.models.interaction import Interaction
from app.models.report import Report
from app.models.task import Task

# Hosted weight overrides (graceful fallback to defaults)
try:
    from app.hosted.weights import TRUST_WEIGHTS as _HOSTED_TRUST_WEIGHTS
except ImportError:
    _HOSTED_TRUST_WEIGHTS = None

_DEFAULT_TRUST_WEIGHTS = {
    "verification": {
        "manual_review": 100,
        "workspace": 75,
        "github": 50,
        "domain": 40,
        "email": 25,
        "none": 0,
    },
    "success_rate_7d": 0.30,
    "report_rate_30d": -0.50,
    "human_confirm_success": 0.15,
    "avg_latency_factor": -0.05,
    "cancel_rate": -0.10,
}

TRUST_WEIGHTS = _HOSTED_TRUST_WEIGHTS if _HOSTED_TRUST_WEIGHTS is not None else _DEFAULT_TRUST_WEIGHTS


async def compute_trust_signals(db: AsyncSession, agent_id: str) -> dict:
    """Compute all trust signals for an agent (spec §14.2)."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Get agent
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return {}

    # Verification level weight
    try:
        ver_level = VerificationLevel(agent.verification_level)
        verification_weight = VERIFICATION_WEIGHTS.get(ver_level, 0)
    except ValueError:
        verification_weight = 0

    # Success rate (7d)
    interactions_7d = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Interaction.outcome == "success").label("success"),
        ).where(
            Interaction.to_agent_id == agent_id,
            Interaction.created_at > seven_days_ago,
        )
    )
    row = interactions_7d.first()
    total_7d = row.total if row else 0
    success_7d = row.success if row else 0
    success_rate_7d = success_7d / total_7d if total_7d > 0 else 1.0

    # Report rate (30d)
    report_count_result = await db.execute(
        select(func.count()).select_from(Report).where(
            Report.reported_agent_id == agent_id,
            Report.created_at > thirty_days_ago,
        )
    )
    report_count_30d = report_count_result.scalar() or 0

    # Tasks received (30d) for normalization
    tasks_received_result = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.created_at > thirty_days_ago,
        )
    )
    tasks_received_30d = tasks_received_result.scalar() or 0
    report_rate_30d = report_count_30d / max(tasks_received_30d, 1)

    # Human confirm success rate
    confirm_total = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.requires_human_confirm == True,  # noqa: E712
            Task.status.in_(["completed", "cancelled", "expired"]),
        )
    )
    confirm_total_count = confirm_total.scalar() or 0

    confirm_success = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.requires_human_confirm == True,  # noqa: E712
            Task.status == "completed",
        )
    )
    confirm_success_count = confirm_success.scalar() or 0
    human_confirm_success_rate = (
        confirm_success_count / confirm_total_count
        if confirm_total_count > 0 else 1.0
    )

    # Average response latency (from interactions)
    latency_result = await db.execute(
        select(func.avg(Interaction.latency_ms)).where(
            Interaction.to_agent_id == agent_id,
            Interaction.latency_ms.isnot(None),
        )
    )
    avg_latency_ms = latency_result.scalar() or 0

    # Cancel/expire rate (30d)
    cancel_expire_result = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.created_at > thirty_days_ago,
            Task.status.in_(["cancelled", "expired"]),
        )
    )
    cancel_expire_count = cancel_expire_result.scalar() or 0
    cancel_expire_rate_30d = cancel_expire_count / max(tasks_received_30d, 1)

    return {
        "verification_weight": verification_weight,
        "success_rate_7d": round(success_rate_7d, 4),
        "report_rate_30d": round(report_rate_30d, 4),
        "human_confirm_success_rate": round(human_confirm_success_rate, 4),
        "avg_latency_ms": round(avg_latency_ms, 2),
        "cancel_expire_rate_30d": round(cancel_expire_rate_30d, 4),
        "total_interactions_7d": total_7d,
        "total_interactions_30d": tasks_received_30d,
        "report_count_30d": report_count_30d,
    }


def compute_trust_score(signals: dict) -> float:
    """Compute composite trust score from signals (0.0 to 100.0).

    Weighted formula:
    - verification_weight: 25%
    - success_rate_7d: 25%
    - report_rate_30d: -20%
    - human_confirm_success_rate: 15%
    - cancel_expire_rate_30d: -15%
    """
    if not signals:
        return 0.0

    # Normalize verification weight (0-4 → 0-1)
    ver_norm = min(signals.get("verification_weight", 0) / 4.0, 1.0)

    score = (
        ver_norm * 25
        + signals.get("success_rate_7d", 1.0) * 25
        - signals.get("report_rate_30d", 0.0) * 20
        + signals.get("human_confirm_success_rate", 1.0) * 15
        - signals.get("cancel_expire_rate_30d", 0.0) * 15
    )

    return round(max(0.0, min(100.0, score)), 2)


async def get_trust_summary(db: AsyncSession, agent_id: str) -> dict:
    """Get a public-facing trust summary for an agent (spec §14.3).

    Shows:
    - is_verified
    - in_network (requires viewer context — not computed here)
    - recent_success
    - trust_score
    """
    signals = await compute_trust_signals(db, agent_id)
    score = compute_trust_score(signals)

    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()

    return {
        "is_verified": agent.verification_level != "none" if agent else False,
        "verification_level": agent.verification_level if agent else "none",
        "trust_score": score,
        "success_rate_7d": signals.get("success_rate_7d", 1.0),
        "total_interactions_7d": signals.get("total_interactions_7d", 0),
        "report_count_30d": signals.get("report_count_30d", 0),
    }


async def compute_popularity_signals(db: AsyncSession, agent_id: str) -> dict:
    """Compute popularity signals (separate from trust, spec §14.1)."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Tasks received count (all time and 7d)
    tasks_all_result = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
        )
    )
    tasks_all = tasks_all_result.scalar() or 0

    tasks_7d_result = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.created_at > seven_days_ago,
        )
    )
    tasks_7d = tasks_7d_result.scalar() or 0

    # Pull actual counters from activity_service
    from app.services import activity_service
    profile_views = activity_service.get_profile_views(agent_id)
    search_appearances = activity_service.get_search_appearances(agent_id)

    return {
        "task_received_count": tasks_all,
        "task_received_7d": tasks_7d,
        "profile_views_7d": profile_views,
        "search_appearances_7d": search_appearances,
    }
