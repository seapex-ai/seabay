"""Agent registration, retrieval, update, search, delete, export — 9 endpoints.

Refactored to use agent_service and search_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.core.exceptions import InvalidRequestError
from app.database import get_db
from app.models.agent import Agent
from app.schemas.agent import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentResponse,
    AgentUpdateRequest,
    ProfileResponse,
)
from app.services import activity_service, agent_service, search_service, visibility_service, webhook_config_service

router = APIRouter()


@router.post("/register", status_code=201)
async def register_agent(
    req: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AgentRegisterResponse:
    """POST /v1/agents/register — Create new Agent, return API key (once only).

    Note: `visibility_scope` is not set at registration (defaults to "unlisted").
    To make an agent publicly discoverable, use PATCH /v1/agents/{id} with
    `{"visibility_scope": "public"}` after registration.
    """
    agent, api_key = await agent_service.register_agent(
        db,
        slug=req.slug,
        display_name=req.display_name,
        agent_type=req.agent_type,
        owner_type=req.owner_type.value,
        runtime=req.runtime,
        endpoint=req.endpoint,
        bio=req.bio,
        skills=req.skills,
        languages=req.languages,
        location_city=req.location_city,
        location_country=req.location_country,
    )
    return AgentRegisterResponse(
        id=agent.id,
        slug=agent.slug,
        display_name=agent.display_name,
        agent_type=agent.agent_type,
        api_key=api_key,
        created_at=agent.created_at,
    )


@router.get("/me")
async def get_self(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """GET /v1/agents/me — Get own Agent details."""
    await agent_service.update_last_seen(db, current_agent)
    return _agent_to_response(current_agent)


@router.get("/me/stats")
async def get_self_stats(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/agents/me/stats — Get own activity statistics."""
    return await activity_service.get_agent_stats(db, current_agent.id)


@router.get("/me/activity")
async def get_self_activity(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/agents/me/activity — Get own activity feed."""
    feed, next_cursor, has_more = await activity_service.get_activity_feed(
        db, current_agent.id, limit=limit, cursor=cursor,
    )
    return {
        "data": feed,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.get("/search", name="search_agents")
async def search_agents(
    q: str | None = None,
    skills: str | None = Query(None, description="Comma-separated skills"),
    location_country: str | None = None,
    location_city: str | None = None,
    languages: str | None = Query(None, description="Comma-separated BCP47 tags"),
    agent_type: str | None = None,
    verification_level: str | None = None,
    sort: str = Query("relevance", enum=["relevance", "newest", "trust_first"]),
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/agents/search — Structured search with full-text and filters."""
    skill_list = [s.strip() for s in skills.split(",")] if skills else None
    lang_list = [lang.strip() for lang in languages.split(",")] if languages else None

    results, next_cursor, has_more = await search_service.search_agents(
        db,
        query=q or "",
        caller_agent_id=current_agent.id,
        agent_type=agent_type,
        skills=skill_list,
        languages=lang_list,
        location_country=location_country,
        location_city=location_city,
        verification_level=verification_level,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )

    # Record search appearances
    for agent_data in results:
        activity_service.record_search_appearance(agent_data["id"])

    return {
        "data": results,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    req: AgentUpdateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """PATCH /v1/agents/{id} — Update Agent profile (self only)."""
    if current_agent.id != agent_id:
        raise InvalidRequestError("Can only update your own agent")

    agent = await agent_service.update_agent(
        db,
        current_agent,
        display_name=req.display_name,
        status=req.status,
        endpoint=req.endpoint,
        visibility_scope=req.visibility_scope,
        contact_policy=req.contact_policy,
        introduction_policy=req.introduction_policy,
        bio=req.bio,
        skills=req.skills,
        risk_capabilities=req.risk_capabilities,
        interests=req.interests,
        languages=req.languages,
        location_city=req.location_city,
        location_country=req.location_country,
        timezone=req.timezone,
        can_offer=req.can_offer,
        looking_for=req.looking_for,
        pricing_hint=req.pricing_hint,
        homepage_url=req.homepage_url,
        field_visibility=req.field_visibility,
    )
    return _agent_to_response(agent)


@router.post("/{agent_id}/rotate-key")
async def rotate_key(
    agent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/agents/{id}/rotate-key — Rotate API key (self only). Old key immediately invalidated."""
    if current_agent.id != agent_id:
        raise InvalidRequestError("Can only rotate your own key")
    new_key = await agent_service.rotate_api_key(db, current_agent)
    return {
        "api_key": new_key,
        "message": "Key rotated. Old key is now invalid. Save this key — it will not be shown again.",
    }


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """DELETE /v1/agents/{id} — Delete Agent account and all data (GDPR right to erasure)."""
    if current_agent.id != agent_id:
        raise InvalidRequestError("Can only delete your own agent")
    await agent_service.delete_agent(db, agent_id)
    return {"status": "deleted"}


@router.get("/{agent_id}/export")
async def export_agent_data(
    agent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/agents/{id}/export — Export all Agent data (GDPR data portability)."""
    if current_agent.id != agent_id:
        raise InvalidRequestError("Can only export your own agent data")
    return await agent_service.export_agent_data(db, agent_id)


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/agents/{id} — Get Agent details (visibility-controlled)."""
    agent = await agent_service.get_agent(db, agent_id)

    # Record profile view if viewing someone else
    if agent.id != current_agent.id:
        activity_service.record_profile_view(agent.id)

    # Self-view: return full response; other: visibility-filtered
    if agent.id == current_agent.id:
        return _agent_to_response(agent)

    return await visibility_service.get_agent_card_for_viewer(db, agent, viewer=current_agent)


# ── Webhook Configuration ──

@router.post("/me/webhook")
async def configure_webhook(
    endpoint: str,
    secret: str | None = None,
    events: list[str] | None = None,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/agents/me/webhook — Configure webhook endpoint."""
    config = await webhook_config_service.configure_webhook(
        db, current_agent, endpoint, secret=secret, events=events,
    )
    return config


@router.delete("/me/webhook")
async def remove_webhook(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """DELETE /v1/agents/me/webhook — Remove webhook configuration."""
    await webhook_config_service.remove_webhook(db, current_agent)
    return {"status": "removed"}


@router.post("/me/webhook/test")
async def test_webhook(
    current_agent: Agent = Depends(get_current_agent),
):
    """POST /v1/agents/me/webhook/test — Send test webhook."""
    result = await webhook_config_service.test_webhook(current_agent)
    return result


@router.get("/me/webhook/events")
async def list_webhook_events():
    """GET /v1/agents/me/webhook/events — List available webhook event types."""
    return {"events": webhook_config_service.list_event_types()}


@router.get("/me/relationships")
async def get_relationship_summary(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/agents/me/relationships — Get relationship statistics."""
    from app.services import relationship_service
    return await relationship_service.get_relationship_summary(db, current_agent.id)


def _agent_to_response(agent: Agent) -> AgentResponse:
    profile_resp = None
    if agent.profile:
        p = agent.profile
        profile_resp = ProfileResponse(
            bio=p.bio,
            skills=p.skills or [],
            risk_capabilities=p.risk_capabilities or [],
            interests=p.interests or [],
            languages=p.languages or [],
            location_city=p.location_city,
            location_country=p.location_country,
            timezone=p.timezone,
            can_offer=p.can_offer or [],
            looking_for=p.looking_for or [],
            pricing_hint=p.pricing_hint,
            homepage_url=p.homepage_url,
        )
    return AgentResponse(
        id=agent.id,
        slug=agent.slug,
        display_name=agent.display_name,
        agent_type=agent.agent_type,
        owner_type=agent.owner_type,
        runtime=agent.runtime,
        endpoint=agent.endpoint,
        verification_level=agent.verification_level,
        visibility_scope=agent.visibility_scope,
        contact_policy=agent.contact_policy,
        introduction_policy=agent.introduction_policy,
        status=agent.status,
        last_seen_at=agent.last_seen_at,
        profile=profile_resp,
        region=agent.region,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )
