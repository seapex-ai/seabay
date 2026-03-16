"""New account restrictions service — first 7 days limitations (spec §15.1).

Open-Core: Reference implementation for account-age-based restrictions.
Production deployments may override windows and limits via app.hosted/services/.

New accounts (< 7 days old) have reduced daily limits:
- Task initiation: 10/day (vs 20/day for established)
- First contact: 2/day (vs 5/day)
- Cannot create circles
- Cannot initiate introductions

After 7 days: limits are upgraded automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.exceptions import ForbiddenError
from app.models.agent import Agent

logger = logging.getLogger(__name__)

# New account window (spec §15.1)
NEW_ACCOUNT_DAYS = 7

# Daily limits for new accounts
NEW_ACCOUNT_LIMITS = {
    "new_direct_task": 10,        # vs 20 for established
    "first_contact": 2,           # vs 5 for established
    "introduction_request": 2,    # reduced for new accounts (spec: 2/day)
    "circle_create": 0,           # disabled for new accounts
    "circle_request": 3,          # vs 5 for established
}

# Daily limits for established accounts
ESTABLISHED_LIMITS = {
    "new_direct_task": 20,
    "first_contact": 5,
    "introduction_request": 3,
    "circle_create": 5,
    "circle_request": 5,
}


def is_new_account(agent: Agent) -> bool:
    """Check if an agent is within the new account window."""
    if not agent.created_at:
        return True
    age = datetime.now(timezone.utc) - agent.created_at.replace(tzinfo=timezone.utc)
    return age < timedelta(days=NEW_ACCOUNT_DAYS)


def get_daily_limit(agent: Agent, action_type: str) -> int:
    """Get the daily limit for an action type, considering account age."""
    if is_new_account(agent):
        return NEW_ACCOUNT_LIMITS.get(action_type, 5)
    return ESTABLISHED_LIMITS.get(action_type, 20)


def check_new_account_restriction(agent: Agent, action_type: str) -> None:
    """Check if a new account is restricted from performing an action.

    Raises ForbiddenError if the action is not allowed.
    """
    if not is_new_account(agent):
        return

    if action_type == "circle_create":
        raise ForbiddenError(
            "New accounts cannot create circles. "
            "Please wait until your account is 7 days old."
        )

    # introduction_request is allowed for new accounts with reduced limit (2/day)
    # budget_service enforces the reduced limit via NEWBIE_LIMITS


def get_account_status(agent: Agent) -> dict:
    """Get account maturity status and applicable limits."""
    new = is_new_account(agent)
    limits = NEW_ACCOUNT_LIMITS if new else ESTABLISHED_LIMITS

    age_days = 0
    if agent.created_at:
        age = datetime.now(timezone.utc) - agent.created_at.replace(tzinfo=timezone.utc)
        age_days = age.days

    return {
        "is_new_account": new,
        "account_age_days": age_days,
        "days_until_established": max(0, NEW_ACCOUNT_DAYS - age_days),
        "daily_limits": limits,
        "restrictions": {
            "can_create_circles": not new,
            "can_initiate_introductions": True,  # allowed with reduced limit (2/day)
        },
    }
