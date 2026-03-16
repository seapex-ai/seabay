"""Report service — intake, threshold detection, auto-suspend.

Open-Core: Reference implementation for abuse report intake and thresholds.
Production deployments may override thresholds via app.hosted/services/.

Covers spec §15.2 (report reasons), §5.1 (report handling thresholds).

Default thresholds:
- 3+ independent reports from different agents → manual review
- 1 report from verification_level >= github → priority queue
- 5+ reports in 24h on same agent → auto-suspend + review
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.enums import VERIFICATION_WEIGHTS, VerificationLevel
from app.models.report import Report

logger = logging.getLogger(__name__)


async def create_report(
    db: AsyncSession,
    reporter: Agent,
    reported_agent_id: str,
    reason_code: str,
    notes: str | None = None,
    task_id: str | None = None,
) -> Report:
    """Create a new abuse report and check auto-moderation thresholds."""
    if reported_agent_id == reporter.id:
        raise InvalidRequestError("Cannot report self")

    # Verify target exists
    target_result = await db.execute(
        select(Agent).where(Agent.id == reported_agent_id)
    )
    target = target_result.scalar_one_or_none()
    if not target:
        raise NotFoundError("Agent")

    # Validate reason code
    valid_reasons = {"spam", "impersonation", "unsafe_request", "policy_violation", "harassment", "other"}
    if reason_code not in valid_reasons:
        raise InvalidRequestError(
            f"Invalid reason_code. Must be one of: {', '.join(sorted(valid_reasons))}"
        )

    # Check for duplicate report
    existing = await db.execute(
        select(Report).where(
            Report.reporter_agent_id == reporter.id,
            Report.reported_agent_id == reported_agent_id,
            Report.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise InvalidRequestError("You already have a pending report on this agent")

    report = Report(
        id=generate_id("report"),
        reporter_agent_id=reporter.id,
        reported_agent_id=reported_agent_id,
        task_id=task_id,
        reason_code=reason_code,
        notes=notes,
        reporter_verification_level=reporter.verification_level,
    )
    db.add(report)
    await db.flush()

    # Check auto-moderation thresholds
    await _check_thresholds(db, target, reporter)

    return report


async def _check_thresholds(
    db: AsyncSession,
    target: Agent,
    reporter: Agent,
) -> None:
    """Check report thresholds and take auto-moderation actions."""
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)

    # Count pending reports for this agent
    total_result = await db.execute(
        select(func.count()).select_from(Report).where(
            Report.reported_agent_id == target.id,
            Report.status == "pending",
        )
    )
    total_pending = total_result.scalar() or 0

    # Count reports in last 24h
    recent_result = await db.execute(
        select(func.count()).select_from(Report).where(
            Report.reported_agent_id == target.id,
            Report.created_at > twenty_four_hours_ago,
        )
    )
    recent_count = recent_result.scalar() or 0

    # 5+ reports in 24h → auto-suspend
    if recent_count >= settings.REPORT_SUSPEND_THRESHOLD:
        target.status = "suspended"
        target.suspended_at = now
        logger.warning(
            "Agent %s auto-suspended: %d reports in 24h",
            target.id, recent_count,
        )
        await db.flush()
        return

    # 3+ independent pending reports → flag for manual review
    if total_pending >= settings.REPORT_SOFT_FREEZE_THRESHOLD:
        # Count distinct reporters
        distinct_result = await db.execute(
            select(func.count(func.distinct(Report.reporter_agent_id))).where(
                Report.reported_agent_id == target.id,
                Report.status == "pending",
            )
        )
        distinct_reporters = distinct_result.scalar() or 0
        if distinct_reporters >= settings.REPORT_SOFT_FREEZE_THRESHOLD:
            logger.warning(
                "Agent %s flagged for review: %d independent reports",
                target.id, distinct_reporters,
            )

    # 1 report from verified reporter (github+) → priority queue
    try:
        reporter_level = VerificationLevel(reporter.verification_level)
        reporter_weight = VERIFICATION_WEIGHTS.get(reporter_level, 0)
    except ValueError:
        reporter_weight = 0

    if reporter_weight >= VERIFICATION_WEIGHTS.get(VerificationLevel.GITHUB, 2):
        logger.info(
            "Priority report from verified reporter %s (level=%s) against %s",
            reporter.id, reporter.verification_level, target.id,
        )


async def get_reports_for_agent(
    db: AsyncSession,
    agent_id: str,
    status: str | None = None,
) -> list[Report]:
    """Get all reports for a specific agent."""
    stmt = select(Report).where(Report.reported_agent_id == agent_id)
    if status:
        stmt = stmt.where(Report.status == status)
    stmt = stmt.order_by(Report.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def review_report(
    db: AsyncSession,
    report_id: str,
    action: str,
    reviewer_id: str,
) -> Report:
    """Review a report: action can be 'actioned' or 'dismissed'."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report")

    if action not in ("actioned", "dismissed"):
        raise InvalidRequestError("Action must be 'actioned' or 'dismissed'")

    report.status = action
    report.reviewed_by = reviewer_id
    report.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return report
