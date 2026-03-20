"""Verification service — email, github, domain, workspace verification flows.

Handles all verification lifecycle logic:
- Code generation and expiry
- Verification completion and agent level update
- Highest verification level computation
- DNS TXT record lookup for domain/workspace verification
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.enums import VERIFICATION_WEIGHTS, VerificationLevel
from app.models.verification import Verification

logger = logging.getLogger(__name__)


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
) -> Verification:
    """Complete domain verification (DNS lookup confirmation).

    When DOMAIN_VERIFICATION_AUTO is True (dev default): auto-verify without DNS lookup.
    When False (production): perform actual DNS TXT record lookup.
    """
    verification = await _get_verification(db, verification_id, agent.id, "domain")
    _check_pending(verification)

    domain = verification.identifier
    expected_value = verification.verification_code

    if not settings.DOMAIN_VERIFICATION_AUTO:
        # Production: perform actual DNS TXT lookup
        dns_verified = await _check_dns_txt_record(f"_seabay.{domain}", expected_value)
        if not dns_verified:
            raise InvalidRequestError(
                "DNS record not found. Please add the TXT record "
                f"'_seabay.{domain}' with value '{expected_value}' and retry."
            )

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


async def start_workspace_verification(
    db: AsyncSession,
    agent_id: str,
    workspace_domain: str,
) -> tuple[Verification, str]:
    """Start workspace verification by domain ownership.

    The agent must prove they belong to the workspace by adding a DNS TXT
    record under _seabay-workspace.<domain>. Returns (verification, txt_value).
    """
    txt_value = f"seabay-workspace={secrets.token_urlsafe(24)}"

    verification = Verification(
        id=generate_id("verification"),
        agent_id=agent_id,
        method="workspace",
        status="pending",
        identifier=workspace_domain,
        verification_code=txt_value,
        code_expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        extra_metadata={"workspace_domain": workspace_domain},
    )
    db.add(verification)
    await db.flush()
    return verification, txt_value


async def complete_workspace_verification(
    db: AsyncSession,
    agent_id: str,
    verification_id: str,
) -> Verification:
    """Complete workspace verification by confirming DNS record.

    Uses the same DNS lookup logic and DOMAIN_VERIFICATION_AUTO flag
    as domain verification.
    """
    verification = await _get_verification(db, verification_id, agent_id, "workspace")
    _check_pending(verification)

    domain = verification.identifier
    expected_value = verification.verification_code

    if not settings.DOMAIN_VERIFICATION_AUTO:
        # Production: perform actual DNS TXT lookup
        dns_verified = await _check_dns_txt_record(
            f"_seabay-workspace.{domain}", expected_value,
        )

        if not dns_verified:
            raise InvalidRequestError(
                "DNS record not found. Please add the TXT record "
                f"'_seabay-workspace.{domain}' with value '{expected_value}' and retry."
            )

    verification.status = "verified"
    verification.verified_at = datetime.now(timezone.utc)

    # Update agent verification level
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent:
        await _update_agent_verification_level(db, agent)

    await db.flush()
    return verification


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


# ── DNS Lookup ──

async def _check_dns_txt_record(record_name: str, expected_value: str) -> bool:
    """Check if a DNS TXT record exists with the expected value.

    Tries dns.resolver first, falls back to subprocess dig/nslookup.
    """
    # Try dns.resolver (if dnspython is installed)
    try:
        import dns.resolver

        def _resolve():
            try:
                answers = dns.resolver.resolve(record_name, "TXT")
                for rdata in answers:
                    for txt_string in rdata.strings:
                        if txt_string.decode("utf-8").strip() == expected_value:
                            return True
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                pass
            except Exception as e:
                logger.warning("dns.resolver error for %s: %s", record_name, e)
            return False

        return await asyncio.get_event_loop().run_in_executor(None, _resolve)
    except ImportError:
        logger.info("dnspython not installed, falling back to subprocess dig")

    # Fallback: use dig command
    try:
        result = await asyncio.create_subprocess_exec(
            "dig", "+short", "TXT", record_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)
        output = stdout.decode("utf-8").strip()
        # dig returns TXT values in quotes: "seabay-verify=xxx"
        for line in output.split("\n"):
            cleaned = line.strip().strip('"')
            if cleaned == expected_value:
                return True
    except FileNotFoundError:
        logger.info("dig not found, trying nslookup")
    except Exception as e:
        logger.warning("dig subprocess error: %s", e)

    # Final fallback: nslookup
    try:
        result = await asyncio.create_subprocess_exec(
            "nslookup", "-type=TXT", record_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)
        output = stdout.decode("utf-8")
        if expected_value in output:
            return True
    except Exception as e:
        logger.warning("nslookup subprocess error: %s", e)

    return False


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
