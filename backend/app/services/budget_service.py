"""Anti-spam budget service — daily rate budgets for personal agents.

Open-Core: Reference implementation with default budget limits.
The production version with tuned limits is in app/hosted/services/.

Covers spec §15.1 (anti-harassment budgets).

Budgets (personal agents only):
- new_direct_task: 5/day (3/day for new users < 7d)
- introduction_request: 3/day (2/day for new users)
- circle_request: 5/day (3/day for new users)

Service agents are NOT subject to budget.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import InvalidRequestError
from app.models.agent import Agent
from app.models.rate_limit_budget import RateLimitBudget

# Hosted budget overrides (graceful fallback to defaults)
try:
    from app.hosted.weights import BUDGET_LIMITS as _HOSTED_BUDGET_LIMITS
except ImportError:
    _HOSTED_BUDGET_LIMITS = None

BUDGET_LIMITS = {
    "new_direct_task": (
        _HOSTED_BUDGET_LIMITS["personal_tasks_per_day"]
        if _HOSTED_BUDGET_LIMITS else settings.BUDGET_NEW_DIRECT_TASK_DAILY
    ),
    "introduction_request": settings.BUDGET_INTRODUCTION_DAILY,
    "circle_request": settings.BUDGET_CIRCLE_REQUEST_DAILY,
}

# New user multiplier (< 7 days old) → reduced limits
NEWBIE_LIMITS = {
    "new_direct_task": (
        _HOSTED_BUDGET_LIMITS["new_account_tasks_per_day"]
        if _HOSTED_BUDGET_LIMITS else 3
    ),
    "introduction_request": (
        _HOSTED_BUDGET_LIMITS.get("personal_first_contacts_per_day", 2)
        if _HOSTED_BUDGET_LIMITS else 2
    ),
    "circle_request": 3,
}


async def check_budget(
    db: AsyncSession,
    agent: Agent,
    budget_type: str,
) -> None:
    """Check if the agent is within their daily budget.

    Service agents bypass budget checks.
    Raises InvalidRequestError if budget exceeded.
    """
    # Service agents are exempt
    if agent.agent_type == "service":
        return

    # Determine limit based on account age
    now = datetime.now(timezone.utc)
    is_newbie = False
    if agent.created_at:
        try:
            created = agent.created_at
            if isinstance(created, str):
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if (now - created).days < 7:
                is_newbie = True
        except (ValueError, TypeError):
            pass

    if is_newbie:
        max_allowed = NEWBIE_LIMITS.get(budget_type, 3)
    else:
        max_allowed = BUDGET_LIMITS.get(budget_type, 5)

    # Count today's usage
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(RateLimitBudget).where(
            RateLimitBudget.agent_id == agent.id,
            RateLimitBudget.budget_type == budget_type,
            RateLimitBudget.window_start >= window_start,
        )
    )
    budget = result.scalar_one_or_none()

    current_count = budget.count if budget else 0
    if current_count >= max_allowed:
        raise InvalidRequestError(
            f"Daily {budget_type} budget exceeded ({current_count}/{max_allowed})"
        )


async def increment_budget(
    db: AsyncSession,
    agent: Agent,
    budget_type: str,
) -> int:
    """Increment the daily budget counter. Returns new count."""
    if agent.agent_type == "service":
        return 0

    now = datetime.now(timezone.utc)
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(RateLimitBudget).where(
            RateLimitBudget.agent_id == agent.id,
            RateLimitBudget.budget_type == budget_type,
            RateLimitBudget.window_start == window_start,
        )
    )
    budget = result.scalar_one_or_none()

    if budget:
        budget.count += 1
        new_count = budget.count
    else:
        is_newbie = False
        if agent.created_at:
            try:
                created = agent.created_at
                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if (now - created).days < 7:
                    is_newbie = True
            except (ValueError, TypeError):
                pass

        max_allowed = (
            NEWBIE_LIMITS.get(budget_type, 3) if is_newbie
            else BUDGET_LIMITS.get(budget_type, 5)
        )

        budget = RateLimitBudget(
            agent_id=agent.id,
            budget_type=budget_type,
            window_start=window_start,
            count=1,
            max_allowed=max_allowed,
        )
        db.add(budget)
        new_count = 1

    await db.flush()
    return new_count
