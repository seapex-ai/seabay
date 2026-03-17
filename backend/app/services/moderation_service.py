"""Moderation audit helpers for open-core builds.

Open-core exposes audit hooks and appeal-facing primitives, but not production
automation thresholds or enforcement triggers.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

_audit_log: list[dict] = []


async def check_auto_moderation(
    db: AsyncSession,
    reported_agent_id: str,
) -> Optional[str]:
    del db, reported_agent_id
    return None


def _log_audit(
    action: str,
    agent_id: str,
    description: str,
    admin_id: Optional[str] = None,
) -> None:
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
    _log_audit(action, agent_id, description, admin_id)


def get_audit_log(
    agent_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    entries = _audit_log
    if agent_id:
        entries = [e for e in entries if e["agent_id"] == agent_id]
    return entries[-limit:]


def get_moderation_summary() -> dict:
    action_counts: dict[str, int] = defaultdict(int)
    for entry in _audit_log:
        action_counts[entry["action"]] += 1
    return {
        "total_actions": len(_audit_log),
        "by_action": dict(action_counts),
    }


def clear_audit_log() -> None:
    _audit_log.clear()
