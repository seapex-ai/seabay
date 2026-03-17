"""New-account policy hooks for open-core builds.

Open-core does not ship production-grade account-age restrictions. Operators can
add their own policy based on deployment needs.
"""

from __future__ import annotations

from app.models.agent import Agent


def is_new_account(agent: Agent) -> bool:
    del agent
    return False


def get_daily_limit(agent: Agent, action_type: str) -> int:
    del agent, action_type
    return 0


def check_new_account_restriction(agent: Agent, action_type: str) -> None:
    del agent, action_type
    return None


def get_account_status(agent: Agent) -> dict:
    del agent
    return {
        "is_new_account": False,
        "account_age_days": None,
        "days_until_established": None,
        "daily_limits": {},
        "restrictions": {
            "can_create_circles": True,
            "can_initiate_introductions": True,
        },
    }
