"""Organization endpoints — Phase C enterprise management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent, get_db
from app.models.agent import Agent
from app.services import org_service

router = APIRouter()


class _OrgCreate(BaseModel):
    slug: str = Field(max_length=64)
    display_name: str = Field(max_length=200)
    description: str | None = Field(None, max_length=2000)
    domain: str | None = Field(None, max_length=200)


class _OrgUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    domain: str | None = Field(None, max_length=200)
    default_contact_policy: str | None = None
    default_visibility: str | None = None
    max_members: int | None = None


class _OrgResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    description: str | None
    owner_agent_id: str
    verification_level: str
    domain: str | None
    default_contact_policy: str
    default_visibility: str
    max_members: int
    status: str
    region: str
    created_at: str
    model_config = {"from_attributes": True}


class _MemberAdd(BaseModel):
    agent_id: str
    role: str = "member"


class _MemberResponse(BaseModel):
    id: str
    org_id: str
    agent_id: str
    role: str
    created_at: str
    model_config = {"from_attributes": True}


class _PolicySet(BaseModel):
    policy_type: str = Field(max_length=30)
    policy_key: str = Field(max_length=50)
    policy_value: str = Field(max_length=2000)


class _PolicyResponse(BaseModel):
    id: str
    org_id: str
    policy_type: str
    policy_key: str
    policy_value: str
    model_config = {"from_attributes": True}


@router.post("", status_code=201, name="create_org")
async def create_org(
    body: _OrgCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.create_org(
        db, current_agent.id, slug=body.slug,
        display_name=body.display_name, description=body.description, domain=body.domain,
    )
    await db.commit()
    return _OrgResponse.model_validate(org)


@router.get("/{org_id}", name="get_org")
async def get_org(org_id: str, db: AsyncSession = Depends(get_db)):
    org = await org_service.get_org(db, org_id)
    return _OrgResponse.model_validate(org)


@router.patch("/{org_id}", name="update_org")
async def update_org(
    org_id: str, body: _OrgUpdate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    org = await org_service.update_org(db, org_id, current_agent.id, **updates)
    await db.commit()
    return _OrgResponse.model_validate(org)


@router.post("/{org_id}/members", status_code=201, name="add_member")
async def add_member(
    org_id: str, body: _MemberAdd,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    mem = await org_service.add_member(
        db, org_id, body.agent_id, body.role, requester_id=current_agent.id,
    )
    await db.commit()
    return _MemberResponse.model_validate(mem)


@router.delete("/{org_id}/members/{agent_id}", status_code=204, name="remove_member")
async def remove_member(
    org_id: str, agent_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    await org_service.remove_member(db, org_id, agent_id, current_agent.id)
    await db.commit()


@router.get("/{org_id}/members", name="list_members")
async def list_members(
    org_id: str,
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    members = await org_service.list_members(db, org_id, limit=limit)
    return {"data": [_MemberResponse.model_validate(m) for m in members]}


@router.post("/{org_id}/policies", status_code=201, name="set_policy")
async def set_policy(
    org_id: str, body: _PolicySet,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    policy = await org_service.set_policy(
        db, org_id, current_agent.id,
        body.policy_type, body.policy_key, body.policy_value,
    )
    await db.commit()
    return _PolicyResponse.model_validate(policy)


@router.get("/{org_id}/policies", name="list_policies")
async def list_policies(org_id: str, db: AsyncSession = Depends(get_db)):
    policies = await org_service.list_policies(db, org_id)
    return {"data": [_PolicyResponse.model_validate(p) for p in policies]}
