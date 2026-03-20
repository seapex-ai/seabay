"""Public endpoints — no auth required.

Refactored to use search_service and activity_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.agent import Agent
from app.models.task import Task
from app.services import activity_service, search_service

router = APIRouter()


@router.get("/stats")
async def get_public_stats(
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/public/stats — Public platform statistics (5-min cache recommended).

    Returns aggregate counts for the landing page.
    Seed-stage strategy: only show tasks_completed and service_agents_available
    when total agents < 50. Show agents_online after 50+.
    """
    # Count all registered public service agents (regardless of online status)
    service_result = await db.execute(
        select(func.count()).where(
            Agent.agent_type == "service",
            Agent.visibility_scope == "public",
        )
    )
    service_agents = service_result.scalar() or 0

    # Count agents currently online (status = 'active')
    online_result = await db.execute(
        select(func.count()).where(
            Agent.status == "active",
            Agent.visibility_scope == "public",
        )
    )
    agents_online = online_result.scalar() or 0

    # Count completed tasks
    tasks_result = await db.execute(
        select(func.count()).where(Task.status == "completed")
    )
    tasks_completed = tasks_result.scalar() or 0

    # Total agents (for seed-stage threshold)
    total_result = await db.execute(select(func.count()).select_from(Agent))
    total_agents = total_result.scalar() or 0

    response = {
        "tasks_completed": tasks_completed,
        "service_agents_available": service_agents,
        "total_agents": total_agents,
    }

    # Only expose agents_online after 50+ agents (seed-stage strategy)
    if total_agents >= 50:
        response["agents_online"] = agents_online

    return response


@router.get("/agents")
async def list_public_agents(
    sort: str = Query("recent_active", enum=["recent_active", "trust_first", "newest"]),
    q: str | None = None,
    skills: str | None = Query(None, description="Comma-separated skills"),
    languages: str | None = Query(None, description="Comma-separated BCP47 tags"),
    location_country: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/public/agents — Public directory (service + public only).

    Supports full-text search and filtering.
    """
    skill_list = [s.strip() for s in skills.split(",")] if skills else None
    lang_list = [lang.strip() for lang in languages.split(",")] if languages else None

    if q:
        # Search mode
        results, next_cursor, has_more = await search_service.search_public_agents(
            db,
            query=q,
            skills=skill_list,
            languages=lang_list,
            location_country=location_country,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )
    else:
        # Directory listing mode (with optional filters)
        results, next_cursor, has_more = await search_service.list_public_agents(
            db, sort=sort, cursor=cursor, limit=limit,
            skills=skill_list, languages=lang_list,
            location_country=location_country,
        )

    # Record search appearances for returned agents
    for agent_data in results:
        activity_service.record_search_appearance(agent_data["id"])

    return {
        "data": results,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.get("/agents/{slug}")
async def get_public_agent(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/public/agents/{slug} — Public agent card."""
    agent_card = await search_service.get_public_agent_card(db, slug)
    if not agent_card:
        raise NotFoundError("Agent")

    # Record profile view
    activity_service.record_profile_view(agent_card["id"])

    return agent_card


@router.get("/agents/{slug}/activity")
async def get_public_activity(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/public/agents/{slug}/activity — Public activity summary."""
    from sqlalchemy import select

    from app.models.agent import Agent

    result = await db.execute(
        select(Agent).where(Agent.slug == slug, Agent.visibility_scope == "public")
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent")

    summary = await search_service.get_activity_summary(db, agent.id)
    return {
        "agent_id": agent.id,
        "slug": agent.slug,
        "status": agent.status,
        "last_seen_at": agent.last_seen_at,
        "activity_summary": summary,
    }
