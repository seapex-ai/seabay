"""Report service for open-core builds.

Open-core includes abuse report intake and review workflow, but does not ship
production auto-enforcement thresholds or private escalation rules.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.report import Report


async def create_report(
    db: AsyncSession,
    reporter: Agent,
    reported_agent_id: str,
    reason_code: str,
    notes: str | None = None,
    task_id: str | None = None,
) -> Report:
    if reported_agent_id == reporter.id:
        raise InvalidRequestError("Cannot report self")

    target_result = await db.execute(
        select(Agent).where(Agent.id == reported_agent_id)
    )
    target = target_result.scalar_one_or_none()
    if not target:
        raise NotFoundError("Agent")

    valid_reasons = {
        "spam",
        "impersonation",
        "unsafe_request",
        "policy_violation",
        "harassment",
        "other",
    }
    if reason_code not in valid_reasons:
        raise InvalidRequestError(
            f"Invalid reason_code. Must be one of: {', '.join(sorted(valid_reasons))}"
        )

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
    return report


async def get_reports_for_agent(
    db: AsyncSession,
    agent_id: str,
    status: str | None = None,
) -> list[Report]:
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
