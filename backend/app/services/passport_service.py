"""Passport Lite service — trust portability across platforms.

Enables agents to carry verified trust signals between Seabay instances
and compatible external platforms. Receipts are cryptographically signed
for tamper detection.

Receipt lifecycle:
1. Issue: Snapshot current trust state into a signed receipt
2. Verify: External party validates receipt signature and expiry
3. Revoke: Agent or admin can revoke a receipt
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import InvalidRequestError, NotFoundError
from app.core.id_generator import generate_id
from app.models.agent import Agent
from app.models.metrics import PassportLiteReceipt
from app.services import trust_service

logger = logging.getLogger(__name__)

# Receipt validity period
RECEIPT_VALIDITY_DAYS = 90

# HMAC signing key from config (MUST be set in production)
SIGNING_KEY = settings.PASSPORT_SIGNING_KEY


async def issue_receipt(
    db: AsyncSession,
    agent_id: str,
    receipt_type: str = "trust_snapshot",
    validity_days: int = RECEIPT_VALIDITY_DAYS,
) -> PassportLiteReceipt:
    """Issue a new Passport Lite receipt for an agent.

    Captures current trust state and signs it for portability.
    """
    # Get agent
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent")

    # Compute current trust signals
    signals = await trust_service.compute_trust_signals(db, agent_id)
    score = trust_service.compute_trust_score(signals)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=validity_days)

    # Build receipt payload
    payload = {
        "agent_id": agent_id,
        "display_name": agent.display_name,
        "trust_score": score,
        "verification_level": agent.verification_level,
        "interaction_count": signals.get("total_interactions_30d", 0),
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "issuer": "seabay",
        "receipt_type": receipt_type,
    }

    # Sign the payload
    signature = _sign_payload(payload)

    receipt = PassportLiteReceipt(
        id=generate_id("receipt"),
        agent_id=agent_id,
        receipt_type=receipt_type,
        issuer="seabay",
        subject_display_name=agent.display_name,
        trust_score_at_issue=score,
        verification_level_at_issue=agent.verification_level,
        interaction_count_at_issue=signals.get("total_interactions_30d", 0),
        issued_at=now,
        expires_at=expires_at,
        signature=signature,
        signature_alg="hmac-sha256",
    )
    db.add(receipt)
    await db.flush()

    logger.info(
        "Issued passport receipt %s for agent %s (score=%.1f)",
        receipt.id, agent_id, score,
    )
    return receipt


async def verify_receipt(
    db: AsyncSession,
    receipt_id: str,
) -> dict:
    """Verify a passport receipt.

    Returns verification result with receipt details.
    """
    result = await db.execute(
        select(PassportLiteReceipt).where(PassportLiteReceipt.id == receipt_id)
    )
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise NotFoundError("Receipt")

    now = datetime.now(timezone.utc)

    # Check revocation
    if receipt.revoked_at:
        return {
            "valid": False,
            "reason": "revoked",
            "receipt_id": receipt.id,
            "revoked_at": receipt.revoked_at,
        }

    # Check expiry
    if receipt.expires_at and now > receipt.expires_at:
        return {
            "valid": False,
            "reason": "expired",
            "receipt_id": receipt.id,
            "expires_at": receipt.expires_at,
        }

    # Verify signature
    payload = {
        "agent_id": receipt.agent_id,
        "display_name": receipt.subject_display_name,
        "trust_score": receipt.trust_score_at_issue,
        "verification_level": receipt.verification_level_at_issue,
        "interaction_count": receipt.interaction_count_at_issue,
        "issued_at": receipt.issued_at.isoformat() if receipt.issued_at else "",
        "expires_at": receipt.expires_at.isoformat() if receipt.expires_at else "",
        "issuer": receipt.issuer,
        "receipt_type": receipt.receipt_type,
    }

    expected_signature = _sign_payload(payload)
    signature_valid = hmac.compare_digest(
        receipt.signature or "", expected_signature,
    )

    return {
        "valid": signature_valid,
        "receipt_id": receipt.id,
        "agent_id": receipt.agent_id,
        "subject_display_name": receipt.subject_display_name,
        "trust_score_at_issue": receipt.trust_score_at_issue,
        "verification_level_at_issue": receipt.verification_level_at_issue,
        "interaction_count_at_issue": receipt.interaction_count_at_issue,
        "issued_at": receipt.issued_at,
        "expires_at": receipt.expires_at,
        "signature_valid": signature_valid,
    }


async def revoke_receipt(
    db: AsyncSession,
    receipt_id: str,
    agent_id: str,
) -> PassportLiteReceipt:
    """Revoke a passport receipt."""
    result = await db.execute(
        select(PassportLiteReceipt).where(
            PassportLiteReceipt.id == receipt_id,
            PassportLiteReceipt.agent_id == agent_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise NotFoundError("Receipt")

    if receipt.revoked_at:
        raise InvalidRequestError("Receipt already revoked")

    receipt.revoked_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("Revoked passport receipt %s for agent %s", receipt_id, agent_id)
    return receipt


async def get_agent_receipts(
    db: AsyncSession,
    agent_id: str,
    include_expired: bool = False,
) -> list[PassportLiteReceipt]:
    """Get all receipts for an agent."""
    stmt = select(PassportLiteReceipt).where(
        PassportLiteReceipt.agent_id == agent_id,
        PassportLiteReceipt.revoked_at.is_(None),
    )

    if not include_expired:
        now = datetime.now(timezone.utc)
        stmt = stmt.where(
            (PassportLiteReceipt.expires_at > now) | (PassportLiteReceipt.expires_at.is_(None))
        )

    stmt = stmt.order_by(PassportLiteReceipt.issued_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _sign_payload(payload: dict) -> str:
    """Create HMAC-SHA256 signature for a receipt payload."""
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    signature = hmac.new(
        SIGNING_KEY.encode(),
        payload_str.encode(),
        hashlib.sha256,
    ).hexdigest()
    return signature
