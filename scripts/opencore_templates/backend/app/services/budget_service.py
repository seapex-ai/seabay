"""Budget service for open-core builds.

Open-core intentionally omits tuned outreach budgets and spam thresholds.
Self-hosted operators can layer their own policy engine on top.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


async def check_budget(
    db: AsyncSession,
    agent: Agent,
    budget_type: str,
) -> None:
    del db, agent, budget_type
    return None


async def increment_budget(
    db: AsyncSession,
    agent: Agent,
    budget_type: str,
) -> int:
    del db, agent, budget_type
    return 0
