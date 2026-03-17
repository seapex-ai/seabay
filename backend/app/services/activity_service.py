"""Activity service — profile views, search appearances, activity feed.

Open-Core: Reference implementation for activity tracking and feed generation.
Production deployments may override storage and aggregation via app.hosted.

Tracks agent activity for popularity metrics and activity feed display.
Uses in-memory counters (V1.5) with periodic DB flush.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction
from app.models.task import Task

logger = logging.getLogger(__name__)

# In-memory counters (V1.5 single-node)
_profile_views: dict[str, int] = defaultdict(int)
_search_appearances: dict[str, int] = defaultdict(int)


def record_profile_view(agent_id: str) -> None:
    """Record a profile view for an agent."""
    _profile_views[agent_id] += 1


def record_search_appearance(agent_id: str) -> None:
    """Record a search appearance for an agent."""
    _search_appearances[agent_id] += 1


def get_profile_views(agent_id: str) -> int:
    """Get profile view count for an agent."""
    return _profile_views.get(agent_id, 0)


def get_search_appearances(agent_id: str) -> int:
    """Get search appearance count for an agent."""
    return _search_appearances.get(agent_id, 0)


def reset_counters() -> None:
    """Reset in-memory counters (called during daily aggregation)."""
    _profile_views.clear()
    _search_appearances.clear()


async def get_activity_feed(
    db: AsyncSession,
    agent_id: str,
    limit: int = 20,
    cursor: Optional[str] = None,
) -> tuple[list[dict], Optional[str], bool]:
    """Get activity feed for an agent.

    Returns recent interactions and task events.
    """
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # Get recent interactions involving this agent
    stmt = (
        select(Interaction)
        .where(
            (Interaction.from_agent_id == agent_id) | (Interaction.to_agent_id == agent_id),
            Interaction.created_at > seven_days_ago,
        )
        .order_by(Interaction.created_at.desc())
    )

    if cursor:
        stmt = stmt.where(Interaction.id < cursor)

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    interactions = list(result.scalars().all())

    has_more = len(interactions) > limit
    if has_more:
        interactions = interactions[:limit]

    feed = []
    for ix in interactions:
        feed.append({
            "id": ix.id,
            "type": "interaction",
            "from_agent_id": ix.from_agent_id,
            "to_agent_id": ix.to_agent_id,
            "outcome": ix.outcome,
            "rating": ix.rating_by_to,
            "created_at": ix.created_at,
        })

    next_cursor = interactions[-1].id if has_more else None
    return feed, next_cursor, has_more


async def get_agent_stats(
    db: AsyncSession,
    agent_id: str,
) -> dict:
    """Get comprehensive stats for an agent."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Tasks sent
    tasks_sent = await db.execute(
        select(func.count()).select_from(Task).where(Task.from_agent_id == agent_id)
    )
    # Tasks received
    tasks_received = await db.execute(
        select(func.count()).select_from(Task).where(Task.to_agent_id == agent_id)
    )
    # Tasks completed (as assignee)
    tasks_completed = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.status == "completed",
        )
    )
    # Tasks in last 7d
    tasks_7d = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.to_agent_id == agent_id,
            Task.created_at > seven_days_ago,
        )
    )

    # Average rating
    avg_rating = await db.execute(
        select(func.avg(Interaction.rating_by_to)).where(
            Interaction.to_agent_id == agent_id,
            Interaction.rating_by_to.isnot(None),
        )
    )

    # Interactions in 30d
    interactions_30d = await db.execute(
        select(func.count()).select_from(Interaction).where(
            (Interaction.from_agent_id == agent_id) | (Interaction.to_agent_id == agent_id),
            Interaction.created_at > thirty_days_ago,
        )
    )

    sent_count = tasks_sent.scalar() or 0
    received_count = tasks_received.scalar() or 0
    completed_count = tasks_completed.scalar() or 0
    recent_count = tasks_7d.scalar() or 0
    rating = avg_rating.scalar()
    interaction_count = interactions_30d.scalar() or 0

    return {
        "agent_id": agent_id,
        "tasks_sent": sent_count,
        "tasks_received": received_count,
        "tasks_completed": completed_count,
        "tasks_last_7d": recent_count,
        "success_rate": round(completed_count / max(received_count, 1), 4),
        "average_rating": round(rating, 2) if rating else None,
        "interactions_30d": interaction_count,
        "profile_views_7d": get_profile_views(agent_id),
        "search_appearances_7d": get_search_appearances(agent_id),
    }
