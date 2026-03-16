"""Moderation service — auto-moderation rules and audit logging.

HOSTED INTELLIGENCE: This service contains operational security thresholds.
The production version with tuned thresholds is in app/hosted/services/.
This file serves as the reference implementation for the open-core repo.

Implements spec §15.3 (report thresholds, auto-actions):
- 1-2 reports: "under observation" (no action)
- 3+ from different agents (24h): auto-suspend + admin notify
- 2+ "impersonation": auto-suspend
- github_verified reporter: priority_review

Audit log tracks all moderation actions for compliance.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.report import Report

logger = logging.getLogger(__name__)

# Thresholds
AUTO_SUSPEND_REPORT_COUNT = 3       # unique reporters in 24h
AUTO_SUSPEND_IMPERSONATION = 2      # impersonation reports
PRIORITY_REVIEW_VERIFICATION = "github"  # reporter level for priority
OBSERVATION_THRESHOLD = 1           # minimum reports for observation

# In-memory audit log (V1.5; production: dedicated table)
_audit_log: list[dict] = []


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
        _log_audit(
            "priority_review",
            reported_agent_id,
            "Priority review triggered by verified reporter",
        )
        return "priority_review"

    # Under observation
    if reporter_count >= OBSERVATION_THRESHOLD:
        _log_audit(
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

    _log_audit(
        "auto_suspend",
        agent_id,
        f"Auto-suspended: {reason}",
    )

    logger.warning(
        "Agent %s auto-suspended: %s", agent_id, reason,
    )


def _log_audit(
    action: str,
    agent_id: str,
    description: str,
    admin_id: Optional[str] = None,
) -> None:
    """Log a moderation audit event."""
    _audit_log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "agent_id": agent_id,
        "description": description,
        "admin_id": admin_id,
    })


def log_admin_action(
    action: str,
    agent_id: str,
    admin_id: str,
    description: str,
) -> None:
    """Log an admin-initiated moderation action."""
    _log_audit(action, agent_id, description, admin_id)


def get_audit_log(
    agent_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Get recent moderation audit log entries."""
    entries = _audit_log
    if agent_id:
        entries = [e for e in entries if e["agent_id"] == agent_id]
    return entries[-limit:]


def get_moderation_summary() -> dict:
    """Get moderation activity summary."""
    action_counts: dict[str, int] = defaultdict(int)
    for entry in _audit_log:
        action_counts[entry["action"]] += 1

    return {
        "total_actions": len(_audit_log),
        "by_action": dict(action_counts),
    }


def clear_audit_log() -> None:
    """Clear audit log (testing only)."""
    _audit_log.clear()
