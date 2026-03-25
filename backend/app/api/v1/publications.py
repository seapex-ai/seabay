"""Publication endpoints — Phase B."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent, get_db
from app.models.agent import Agent
from app.schemas.publication import PublicationCreate, PublicationResponse, PublicationUpdate
from app.services import publication_service

router = APIRouter()


@router.post("", status_code=201, name="create_publication")
async def create_publication(
    body: PublicationCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    pub = await publication_service.create_publication(
        db,
        current_agent.id,
        publication_type=body.publication_type.value,
        title=body.title,
        description=body.description,
        structured_data=body.structured_data,
        tags=body.tags,
        category=body.category,
        price_summary=body.price_summary,
        availability_summary=body.availability_summary,
        location_city=body.location_city,
        location_country=body.location_country,
        visibility_scope=body.visibility_scope.value if body.visibility_scope else "public",
        expires_at=body.expires_at,
    )
    await db.commit()
    return PublicationResponse.model_validate(pub)


@router.get("", name="list_publications")
async def list_publications(
    query: str | None = None,
    publication_type: str | None = None,
    category: str | None = None,
    location_country: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    pubs = await publication_service.search_publications(
        db,
        query=query,
        publication_type=publication_type,
        category=category,
        location_country=location_country,
        limit=limit + 1,
        cursor=cursor,
    )
    has_more = len(pubs) > limit
    if has_more:
        pubs = pubs[:limit]
    return {
        "data": [PublicationResponse.model_validate(p) for p in pubs],
        "has_more": has_more,
        "next_cursor": pubs[-1].id if has_more else None,
    }


@router.get("/mine", name="my_publications")
async def my_publications(
    status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    pubs = await publication_service.list_agent_publications(
        db, current_agent.id, status=status, limit=limit, cursor=cursor,
    )
    return {"data": [PublicationResponse.model_validate(p) for p in pubs]}


@router.get("/{pub_id}", name="get_publication")
async def get_publication(
    pub_id: str,
    db: AsyncSession = Depends(get_db),
):
    pub = await publication_service.get_publication(db, pub_id)
    return PublicationResponse.model_validate(pub)


@router.patch("/{pub_id}", name="update_publication")
async def update_publication(
    pub_id: str,
    body: PublicationUpdate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"]:
        updates["status"] = updates["status"].value
    if "visibility_scope" in updates and updates["visibility_scope"]:
        updates["visibility_scope"] = updates["visibility_scope"].value
    pub = await publication_service.update_publication(db, pub_id, current_agent.id, **updates)
    await db.commit()
    return PublicationResponse.model_validate(pub)


@router.delete("/{pub_id}", status_code=204, name="delete_publication")
async def delete_publication(
    pub_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    await publication_service.delete_publication(db, pub_id, current_agent.id)
    await db.commit()
