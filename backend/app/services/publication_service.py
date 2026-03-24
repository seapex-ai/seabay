"""Publication service — CRUD, search, lifecycle management.

Covers Phase B Publication/Offering domain:
- 6 publication types: service, product, project_opening, event, exchange, request
- Public directory with search and filtering
- Visibility and status management
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.id_generator import generate_id
from app.models.enums import PublicationStatus
from app.models.publication import Publication

logger = logging.getLogger(__name__)


async def create_publication(
    db: AsyncSession,
    agent_id: str,
    *,
    publication_type: str,
    title: str,
    description: str,
    structured_data: dict | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
    price_summary: str | None = None,
    availability_summary: str | None = None,
    location_city: str | None = None,
    location_country: str | None = None,
    visibility_scope: str = "public",
    expires_at: datetime | None = None,
) -> Publication:
    pub = Publication(
        id=generate_id("pub"),
        agent_id=agent_id,
        publication_type=publication_type,
        title=title,
        description=description,
        structured_data=structured_data or {},
        tags=tags or [],
        category=category,
        price_summary=price_summary,
        availability_summary=availability_summary,
        location_city=location_city,
        location_country=location_country,
        visibility_scope=visibility_scope,
        expires_at=expires_at,
    )
    db.add(pub)
    await db.flush()
    logger.info("Publication %s created by agent %s (type=%s)", pub.id, agent_id, publication_type)
    return pub


async def get_publication(db: AsyncSession, pub_id: str) -> Publication:
    result = await db.execute(select(Publication).where(Publication.id == pub_id))
    pub = result.scalar_one_or_none()
    if not pub:
        raise NotFoundError("Publication")
    return pub


async def update_publication(
    db: AsyncSession,
    pub_id: str,
    agent_id: str,
    **updates,
) -> Publication:
    pub = await get_publication(db, pub_id)
    if pub.agent_id != agent_id:
        raise ForbiddenError("Not the owner of this publication")
    for key, value in updates.items():
        if value is not None and hasattr(pub, key):
            setattr(pub, key, value)
    await db.flush()
    return pub


async def delete_publication(db: AsyncSession, pub_id: str, agent_id: str) -> None:
    pub = await get_publication(db, pub_id)
    if pub.agent_id != agent_id:
        raise ForbiddenError("Not the owner of this publication")
    await db.delete(pub)
    await db.flush()
    logger.info("Publication %s deleted by agent %s", pub_id, agent_id)


async def list_agent_publications(
    db: AsyncSession,
    agent_id: str,
    status: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> list[Publication]:
    stmt = select(Publication).where(Publication.agent_id == agent_id)
    if status:
        stmt = stmt.where(Publication.status == status)
    if cursor:
        stmt = stmt.where(Publication.id > cursor)
    stmt = stmt.order_by(Publication.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def search_publications(
    db: AsyncSession,
    *,
    query: str | None = None,
    publication_type: str | None = None,
    category: str | None = None,
    location_country: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> list[Publication]:
    stmt = select(Publication).where(
        Publication.status == PublicationStatus.ACTIVE.value,
        Publication.visibility_scope == "public",
    )

    if query:
        q = f"%{query}%"
        stmt = stmt.where(
            or_(
                Publication.title.ilike(q),
                Publication.description.ilike(q),
            )
        )
    if publication_type:
        stmt = stmt.where(Publication.publication_type == publication_type)
    if category:
        stmt = stmt.where(Publication.category == category)
    if location_country:
        stmt = stmt.where(Publication.location_country == location_country)
    if tags:
        stmt = stmt.where(Publication.tags.overlap(tags))
    if cursor:
        stmt = stmt.where(Publication.id > cursor)

    stmt = stmt.order_by(Publication.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_public_stats(db: AsyncSession) -> dict:
    result = await db.execute(
        select(func.count()).select_from(Publication).where(
            Publication.status == PublicationStatus.ACTIVE.value,
            Publication.visibility_scope == "public",
        )
    )
    return {"active_publications": result.scalar() or 0}
