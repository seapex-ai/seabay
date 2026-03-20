"""Shadow-throttle hooks for open-core builds.

Production delay heuristics and abuse thresholds are intentionally not part of
the public reference distribution.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def check_should_throttle(
    agent_id: str,
    agent_created_at: datetime,
    report_count: int = 0,
    daily_budget_used_pct: float = 0.0,
) -> Optional[float]:
    del agent_id, agent_created_at, report_count, daily_budget_used_pct
    return None


def record_first_contact(agent_id: str) -> None:
    del agent_id
    return None


def is_throttled(agent_id: str) -> bool:
    del agent_id
    return False


def get_throttle_stats() -> dict:
    return {
        "total_throttled": 0,
        "currently_active": 0,
        "tracker_agents": 0,
    }


def clear_throttle(agent_id: str) -> None:
    del agent_id
    return None


def reset_all() -> None:
    return None
