"""Organization service — Phase C team/enterprise management.

Covers:
- Organization CRUD
- Membership management (owner/admin/member/viewer)
- Organization-level policies
- Private registry (org-scoped agent visibility)
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.organization import Organization, OrgMembership, OrgPolicy

logger = logging.getLogger(__name__)


async def create_org(
    db: AsyncSession,
    owner_agent_id: str,
    *,
    slug: str,
    display_name: str,
    description: str | None = None,
    domain: str | None = None,
) -> Organization:
    # Check slug uniqueness
    existing = await db.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        raise InvalidRequestError(f"Organization slug '{slug}' already taken")

    org = Organization(
        id=generate_id("org"),
        slug=slug,
        display_name=display_name,
        description=description,
        owner_agent_id=owner_agent_id,
        domain=domain,
    )
    db.add(org)
    await db.flush()  # persist org first to satisfy FK on org_memberships

    # Auto-add owner as member
    membership = OrgMembership(
        id=generate_id("omem"),
        org_id=org.id,
        agent_id=owner_agent_id,
        role="owner",
    )
    db.add(membership)
    await db.flush()
    logger.info("Organization %s created by %s", org.id, owner_agent_id)
    return org


async def get_org(db: AsyncSession, org_id: str) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization")
    return org


async def get_org_by_slug(db: AsyncSession, slug: str) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == slug))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization")
    return org


async def update_org(
    db: AsyncSession, org_id: str, agent_id: str, **updates,
) -> Organization:
    org = await get_org(db, org_id)
    # Check admin/owner permission
    await _require_role(db, org_id, agent_id, ["owner", "admin"])
    for key, value in updates.items():
        if value is not None and hasattr(org, key):
            setattr(org, key, value)
    await db.flush()
    return org


async def add_member(
    db: AsyncSession, org_id: str, agent_id: str, role: str = "member",
    requester_id: str | None = None,
) -> OrgMembership:
    org = await get_org(db, org_id)
    if requester_id:
        await _require_role(db, org_id, requester_id, ["owner", "admin"])

    # Check member count
    count = await db.execute(
        select(func.count()).select_from(OrgMembership).where(OrgMembership.org_id == org_id)
    )
    if (count.scalar() or 0) >= org.max_members:
        raise ForbiddenError(f"Organization member limit ({org.max_members}) reached")

    # Check not already member
    existing = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.agent_id == agent_id,
        )
    )
    if existing.scalar_one_or_none():
        raise InvalidRequestError("Agent is already a member")

    mem = OrgMembership(
        id=generate_id("omem"),
        org_id=org_id,
        agent_id=agent_id,
        role=role,
    )
    db.add(mem)
    await db.flush()
    logger.info("Agent %s added to org %s as %s", agent_id, org_id, role)
    return mem


async def remove_member(
    db: AsyncSession, org_id: str, agent_id: str, requester_id: str,
) -> None:
    await _require_role(db, org_id, requester_id, ["owner", "admin"])
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.agent_id == agent_id,
        )
    )
    mem = result.scalar_one_or_none()
    if not mem:
        raise NotFoundError("Membership")
    if mem.role == "owner":
        raise ForbiddenError("Cannot remove the organization owner")
    await db.delete(mem)
    await db.flush()


async def list_members(
    db: AsyncSession, org_id: str, limit: int = 100,
) -> list[OrgMembership]:
    result = await db.execute(
        select(OrgMembership).where(OrgMembership.org_id == org_id).limit(limit)
    )
    return list(result.scalars().all())


async def set_policy(
    db: AsyncSession, org_id: str, agent_id: str,
    policy_type: str, policy_key: str, policy_value: str,
) -> OrgPolicy:
    await _require_role(db, org_id, agent_id, ["owner", "admin"])

    # Upsert
    result = await db.execute(
        select(OrgPolicy).where(
            OrgPolicy.org_id == org_id,
            OrgPolicy.policy_type == policy_type,
            OrgPolicy.policy_key == policy_key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.policy_value = policy_value
        await db.flush()
        return existing

    policy = OrgPolicy(
        id=generate_id("opol"),
        org_id=org_id,
        policy_type=policy_type,
        policy_key=policy_key,
        policy_value=policy_value,
    )
    db.add(policy)
    await db.flush()
    return policy


async def list_policies(db: AsyncSession, org_id: str) -> list[OrgPolicy]:
    result = await db.execute(
        select(OrgPolicy).where(OrgPolicy.org_id == org_id)
    )
    return list(result.scalars().all())


async def _require_role(
    db: AsyncSession, org_id: str, agent_id: str, roles: list[str],
) -> OrgMembership:
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.agent_id == agent_id,
        )
    )
    mem = result.scalar_one_or_none()
    if not mem or mem.role not in roles:
        raise ForbiddenError(f"Requires role: {', '.join(roles)}")
    return mem
