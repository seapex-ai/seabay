"""Verification service — email, github, domain verification flows.

Handles all verification lifecycle logic:
- Code generation and expiry
- Verification completion and agent level update
- Highest verification level computation
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.enums import VERIFICATION_WEIGHTS, VerificationLevel
from app.models.verification import Verification


async def start_email_verification(
    db: AsyncSession,
    agent: Agent,
    email: str,
) -> tuple[Verification, str]:
    """Start email verification. Returns (verification, code)."""
    code = secrets.token_urlsafe(6)[:8].upper()
    now = datetime.now(timezone.utc)

    verification = Verification(
        id=generate_id("verification"),
        agent_id=agent.id,
        method="email",
        status="pending",
        identifier=email,
        verification_code=code,
        code_expires_at=now + timedelta(minutes=30),
    )
    db.add(verification)
    await db.flush()
    return verification, code


async def complete_email_verification(
    db: AsyncSession,
    agent: Agent,
    verification_id: str,
    code: str,
) -> Verification:
    """Complete email verification by validating code."""
    verification = await _get_verification(db, verification_id, agent.id, "email")
    _check_pending(verification)
    _check_code_expiry(verification)

    if verification.verification_code != code:
        raise InvalidRequestError("Invalid verification code")

    verification.status = "verified"
    verification.verified_at = datetime.now(timezone.utc)

    await _update_agent_verification_level(db, agent)
    await db.flush()
    return verification


async def start_github_verification(
    db: AsyncSession,
    agent: Agent,
) -> tuple[Verification, str]:
    """Start GitHub OAuth verification. Returns (verification, state_token)."""
    state = secrets.token_urlsafe(32)

    verification = Verification(
        id=generate_id("verification"),
        agent_id=agent.id,
        method="github",
        status="pending",
        verification_code=state,
        code_expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        extra_metadata={"state": state},
    )
    db.add(verification)
    await db.flush()
    return verification, state


async def complete_github_verification(
    db: AsyncSession,
    agent: Agent,
    verification_id: str,
    github_username: str,
    github_id: Optional[str] = None,
) -> Verification:
    """Complete GitHub OAuth verification (callback from OAuth flow)."""
    verification = await _get_verification(db, verification_id, agent.id, "github")
    _check_pending(verification)
    _check_code_expiry(verification)

    verification.status = "verified"
    verification.verified_at = datetime.now(timezone.utc)
    verification.identifier = github_username
    verification.extra_metadata = {
        **(verification.extra_metadata or {}),
        "github_username": github_username,
        "github_id": github_id,
    }

    await _update_agent_verification_level(db, agent)
    await db.flush()
    return verification


async def start_domain_verification(
    db: AsyncSession,
    agent: Agent,
    domain: str,
) -> tuple[Verification, str]:
    """Start DNS TXT domain verification. Returns (verification, txt_value)."""
    txt_value = f"seabay-verify={secrets.token_urlsafe(24)}"

    verification = Verification(
        id=generate_id("verification"),
        agent_id=agent.id,
        method="domain",
        status="pending",
        identifier=domain,
        verification_code=txt_value,
        code_expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
    )
    db.add(verification)
    await db.flush()
    return verification, txt_value


async def complete_domain_verification(
    db: AsyncSession,
    agent: Agent,
    verification_id: str,
    dns_verified: bool = True,
) -> Verification:
    """Complete domain verification (DNS lookup confirmation).

    In V1.5 dev: dns_verified defaults to True (auto-verify).
    Production: perform actual DNS TXT lookup.
    """
    verification = await _get_verification(db, verification_id, agent.id, "domain")
    _check_pending(verification)

    if not dns_verified:
        raise InvalidRequestError("DNS record not found. Please add the TXT record and retry.")

    verification.status = "verified"
    verification.verified_at = datetime.now(timezone.utc)

    await _update_agent_verification_level(db, agent)
    await db.flush()
    return verification


async def get_verifications(
    db: AsyncSession,
    agent_id: str,
    method: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Verification]:
    """List verifications for an agent, optionally filtered."""
    stmt = select(Verification).where(Verification.agent_id == agent_id)
    if method:
        stmt = stmt.where(Verification.method == method)
    if status:
        stmt = stmt.where(Verification.status == status)
    stmt = stmt.order_by(Verification.created_at.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke_verification(
    db: AsyncSession,
    agent: Agent,
    verification_id: str,
) -> Verification:
    """Revoke a previously verified verification."""
    result = await db.execute(
        select(Verification).where(
            Verification.id == verification_id,
            Verification.agent_id == agent.id,
        )
    )
    verification = result.scalar_one_or_none()
    if not verification:
        raise NotFoundError("Verification")

    if verification.status != "verified":
        raise InvalidRequestError(f"Cannot revoke verification in {verification.status} state")

    verification.status = "revoked"
    await _update_agent_verification_level(db, agent)
    await db.flush()
    return verification


async def compute_highest_verification(
    db: AsyncSession,
    agent_id: str,
) -> str:
    """Compute the highest verification level from all verified records."""
    result = await db.execute(
        select(Verification).where(
            Verification.agent_id == agent_id,
            Verification.status == "verified",
        )
    )
    verifications = result.scalars().all()

    if not verifications:
        return "none"

    highest_weight = 0
    highest_level = "none"
    for v in verifications:
        try:
            level = VerificationLevel(v.method)
            weight = VERIFICATION_WEIGHTS.get(level, 0)
            if weight > highest_weight:
                highest_weight = weight
                highest_level = v.method
        except ValueError:
            continue

    return highest_level


# ── Internal Helpers ──

async def _get_verification(
    db: AsyncSession,
    verification_id: str,
    agent_id: str,
    method: str,
) -> Verification:
    """Fetch a verification or raise NotFoundError."""
    result = await db.execute(
        select(Verification).where(
            Verification.id == verification_id,
            Verification.agent_id == agent_id,
            Verification.method == method,
        )
    )
    verification = result.scalar_one_or_none()
    if not verification:
        raise NotFoundError("Verification")
    return verification


def _check_pending(verification: Verification) -> None:
    """Ensure verification is in pending state."""
    if verification.status != "pending":
        raise InvalidRequestError(f"Verification is {verification.status}")


def _check_code_expiry(verification: Verification) -> None:
    """Check if verification code has expired."""
    now = datetime.now(timezone.utc)
    if verification.code_expires_at and now > verification.code_expires_at:
        verification.status = "expired"
        raise InvalidRequestError("Verification code has expired")


async def _update_agent_verification_level(
    db: AsyncSession,
    agent: Agent,
) -> None:
    """Recompute and set agent's verification_level from verified records."""
    highest = await compute_highest_verification(db, agent.id)
    agent.verification_level = highest
