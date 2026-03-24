"""Moderation service — auto-moderation rules and audit logging.

Open-Core: Reference implementation with default moderation thresholds.
Production deployments may override thresholds via app.hosted/services/.

Implements spec \u00a715.3 (report thresholds, auto-actions):
- 1-2 reports: "under observation" (no action)
- 3+ from different agents (24h): auto-suspend + admin notify
- 2+ "impersonation": auto-suspend
- github_verified reporter: priority_review

V1.6: Audit log persisted to DB via audit_logs table (replaces in-memory list).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.audit_log import AuditLog
from app.models.report import Report

logger = logging.getLogger(__name__)

# Hosted threshold overrides (graceful fallback to defaults)
try:
    from app.hosted.weights import MODERATION_THRESHOLDS as _HOSTED_MOD_THRESHOLDS
except ImportError:
    _HOSTED_MOD_THRESHOLDS = None

# Thresholds (use hosted values when available)
AUTO_SUSPEND_REPORT_COUNT = (
    _HOSTED_MOD_THRESHOLDS["auto_suspend_reports"]
    if _HOSTED_MOD_THRESHOLDS else 3
)
AUTO_SUSPEND_IMPERSONATION = (
    _HOSTED_MOD_THRESHOLDS["impersonation_threshold"]
    if _HOSTED_MOD_THRESHOLDS else 2
)
PRIORITY_REVIEW_VERIFICATION = "github"  # reporter level for priority
OBSERVATION_THRESHOLD = 1           # minimum reports for observation


async def check_auto_moderation(
    db: AsyncSession,
    reported_agent_id: str,
) -> Optional[str]:
    """Check if auto-moderation actions should be triggered.

    Returns action taken: "auto_suspended", "priority_review", "observation", or None.
    """
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)

    # Count recent unique reporters
    unique_reporters = await db.execute(
        select(func.count(func.distinct(Report.reporter_agent_id))).where(
            Report.reported_agent_id == reported_agent_id,
            Report.created_at > twenty_four_hours_ago,
        )
    )
    reporter_count = unique_reporters.scalar() or 0

    # Check impersonation reports
    impersonation_count_result = await db.execute(
        select(func.count()).select_from(Report).where(
            Report.reported_agent_id == reported_agent_id,
            Report.reason_code == "impersonation",
        )
    )
    impersonation_count = impersonation_count_result.scalar() or 0

    # Check for priority review (github-verified reporter)
    priority_reporters = await db.execute(
        select(Agent.id).join(
            Report, Report.reporter_agent_id == Agent.id,
        ).where(
            Report.reported_agent_id == reported_agent_id,
            Agent.verification_level == PRIORITY_REVIEW_VERIFICATION,
            Report.created_at > twenty_four_hours_ago,
        )
    )
    has_priority_reporter = priority_reporters.first() is not None

    # Auto-suspend on 3+ unique reporters in 24h
    if reporter_count >= AUTO_SUSPEND_REPORT_COUNT:
        await _auto_suspend(db, reported_agent_id, "multi_report_threshold")
        return "auto_suspended"

    # Auto-suspend on 2+ impersonation reports
    if impersonation_count >= AUTO_SUSPEND_IMPERSONATION:
        await _auto_suspend(db, reported_agent_id, "impersonation_threshold")
        return "auto_suspended"

    # Priority review for verified reporter
    if has_priority_reporter:
        await _log_audit(
            db,
            "priority_review",
            reported_agent_id,
            "Priority review triggered by verified reporter",
        )
        return "priority_review"

    # Under observation
    if reporter_count >= OBSERVATION_THRESHOLD:
        await _log_audit(
            db,
            "observation",
            reported_agent_id,
            f"Under observation: {reporter_count} reporter(s)",
        )
        return "observation"

    return None


async def _auto_suspend(
    db: AsyncSession,
    agent_id: str,
    reason: str,
) -> None:
    """Auto-suspend an agent and log the action."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        return

    if agent.status == "suspended" or agent.status == "banned":
        return  # already suspended/banned

    agent.status = "suspended"
    agent.suspended_at = datetime.now(timezone.utc)
    await db.flush()

    await _log_audit(
        db,
        "auto_suspend",
        agent_id,
        f"Auto-suspended: {reason}",
    )

    logger.warning(
        "Agent %s auto-suspended: %s", agent_id, reason,
    )


async def _log_audit(
    db: AsyncSession,
    action: str,
    target_id: str,
    description: str,
    actor_id: Optional[str] = None,
) -> None:
    """Persist a moderation audit event to the audit_logs table."""
    entry = AuditLog(
        id=generate_id("aud"),
        action=action,
        actor_id=actor_id,
        target_id=target_id,
        details={"description": description},
    )
    db.add(entry)
    await db.flush()


async def log_admin_action(
    db: AsyncSession,
    action: str,
    agent_id: str,
    admin_id: str,
    description: str,
) -> None:
    """Log an admin-initiated moderation action."""
    await _log_audit(db, action, agent_id, description, admin_id)


async def get_audit_log(
    db: AsyncSession,
    agent_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Get recent moderation audit log entries from DB."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if agent_id:
        stmt = stmt.where(AuditLog.target_id == agent_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "action": row.action,
            "actor_id": row.actor_id,
            "target_id": row.target_id,
            "details": row.details,
        }
        for row in rows
    ]


async def get_moderation_summary(db: AsyncSession) -> dict:
    """Get moderation activity summary from DB."""
    total_result = await db.execute(
        select(func.count()).select_from(AuditLog)
    )
    total = total_result.scalar() or 0

    action_rows = await db.execute(
        select(AuditLog.action, func.count()).group_by(AuditLog.action)
    )
    by_action = {row[0]: row[1] for row in action_rows.all()}

    return {
        "total_actions": total,
        "by_action": by_action,
    }
