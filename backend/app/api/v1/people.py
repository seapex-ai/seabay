"""People matching endpoints — Phase B controlled stranger matching."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent, get_db
from app.models.agent import Agent
from app.services import people_service

router = APIRouter()


@router.get("/search", name="search_people")
async def search_people(
    query: str | None = None,
    skills: str | None = None,
    languages: str | None = None,
    location_country: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    skill_list = skills.split(",") if skills else None
    lang_list = languages.split(",") if languages else None
    people = await people_service.search_people(
        db,
        query=query,
        skills=skill_list,
        languages=lang_list,
        location_country=location_country,
        limit=limit,
        cursor=cursor,
    )
    return {"data": people}


class _InterestBody(BaseModel):
    target_agent_id: str
    message: str | None = Field(None, max_length=500)


@router.post("/interest", status_code=201, name="express_interest")
async def express_interest(
    body: _InterestBody,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    result = await people_service.express_interest(
        db, current_agent.id, body.target_agent_id, body.message,
    )
    await db.commit()
    return result
