"""Shadow throttle service — anti-abuse delivery delay (spec §15).

Open-Core: Reference implementation with default anti-abuse delay parameters.
Production deployments may override these parameters via app.hosted/services/.

Instead of silently dropping suspicious requests, delays delivery by
a random 30-120 seconds. The sender does NOT know they are being throttled.

Triggers:
- New account (< 7 days old) exceeding daily budget 80%+
- Agent with 2+ recent reports
- Sudden spike in first-contact tasks (>3 in 1 hour)

Default effects:
- Task delivery delayed by 30-120s random interval
- No error returned to sender
- Admin notified via shadow_throttle event
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Hosted throttle config overrides (graceful fallback to defaults)
try:
    from app.hosted.weights import SHADOW_THROTTLE_CONFIG as _HOSTED_THROTTLE_CONFIG
except ImportError:
    _HOSTED_THROTTLE_CONFIG = None

# Configuration (use hosted values when available)
THROTTLE_MIN_DELAY = (
    _HOSTED_THROTTLE_CONFIG["min_delay_seconds"]
    if _HOSTED_THROTTLE_CONFIG else 30
)
THROTTLE_MAX_DELAY = (
    _HOSTED_THROTTLE_CONFIG["max_delay_seconds"]
    if _HOSTED_THROTTLE_CONFIG else 120
)
NEW_ACCOUNT_DAYS = 7       # days until account is no longer "new"
SPIKE_THRESHOLD = (
    _HOSTED_THROTTLE_CONFIG["trigger_threshold"]
    if _HOSTED_THROTTLE_CONFIG else 3
)
SPIKE_WINDOW = (
    _HOSTED_THROTTLE_CONFIG.get("window_minutes", 10) * 60
    if _HOSTED_THROTTLE_CONFIG else 3600
)
REPORT_THRESHOLD = 2       # reports to trigger throttle

# In-memory state (V1.5 single-node)
_throttled_agents: dict[str, datetime] = {}
_first_contact_tracker: dict[str, list[datetime]] = defaultdict(list)


def check_should_throttle(
    agent_id: str,
    agent_created_at: datetime,
    report_count: int = 0,
    daily_budget_used_pct: float = 0.0,
) -> Optional[float]:
    """Check if an agent's outgoing actions should be shadow-throttled.

    Returns:
        Delay in seconds if throttled, None otherwise.
    """
    now = datetime.now(timezone.utc)
    reasons = []

    # Check new account with high budget usage
    account_age = now - agent_created_at
    if account_age < timedelta(days=NEW_ACCOUNT_DAYS):
        if daily_budget_used_pct >= 0.8:
            reasons.append("new_account_high_usage")

    # Check report count
    if report_count >= REPORT_THRESHOLD:
        reasons.append("reports_threshold")

    # Check first-contact spike
    if _check_spike(agent_id, now):
        reasons.append("first_contact_spike")

    if not reasons:
        return None

    delay = random.uniform(THROTTLE_MIN_DELAY, THROTTLE_MAX_DELAY)
    _throttled_agents[agent_id] = now

    logger.warning(
        "Shadow throttle applied to agent %s: delay=%.1fs reasons=%s",
        agent_id, delay, reasons,
    )
    return delay


def record_first_contact(agent_id: str) -> None:
    """Record a first-contact action for spike detection."""
    now = datetime.now(timezone.utc)
    _first_contact_tracker[agent_id].append(now)

    # Prune old entries
    cutoff = now - timedelta(seconds=SPIKE_WINDOW)
    _first_contact_tracker[agent_id] = [
        t for t in _first_contact_tracker[agent_id] if t > cutoff
    ]


def is_throttled(agent_id: str) -> bool:
    """Check if an agent is currently being shadow-throttled."""
    return agent_id in _throttled_agents


def get_throttle_stats() -> dict:
    """Get current throttle statistics."""
    now = datetime.now(timezone.utc)
    active = {
        k: v for k, v in _throttled_agents.items()
        if (now - v).total_seconds() < THROTTLE_MAX_DELAY
    }
    return {
        "total_throttled": len(_throttled_agents),
        "currently_active": len(active),
        "tracker_agents": len(_first_contact_tracker),
    }


def clear_throttle(agent_id: str) -> None:
    """Clear throttle state for an agent (admin action)."""
    _throttled_agents.pop(agent_id, None)
    _first_contact_tracker.pop(agent_id, None)


def reset_all() -> None:
    """Reset all throttle state (testing only)."""
    _throttled_agents.clear()
    _first_contact_tracker.clear()


def _check_spike(agent_id: str, now: datetime) -> bool:
    """Check if agent has a first-contact spike."""
    cutoff = now - timedelta(seconds=SPIKE_WINDOW)
    recent = [t for t in _first_contact_tracker.get(agent_id, []) if t > cutoff]
    return len(recent) >= SPIKE_THRESHOLD
