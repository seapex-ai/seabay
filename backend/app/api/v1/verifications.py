"""Verification endpoints — email, github, domain.

Delegates all business logic to verification_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.database import get_db
from app.models.agent import Agent
from app.services import verification_service

router = APIRouter()


@router.post("/email/start", status_code=201)
async def start_email_verification(
    email: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/verifications/email/start — Send verification email."""
    verification, code = await verification_service.start_email_verification(
        db, current_agent, email,
    )
    return {
        "verification_id": verification.id,
        "email": email,
        "status": "pending",
        "message": "Verification code sent to email",
        # DEV ONLY — remove in production:
        "_dev_code": code,
    }


@router.post("/email/complete")
async def complete_email_verification(
    verification_id: str,
    code: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/verifications/email/complete — Verify email code."""
    verification = await verification_service.complete_email_verification(
        db, current_agent, verification_id, code,
    )
    return {"verification_id": verification.id, "status": "verified"}


@router.post("/github/start", status_code=201)
async def start_github_verification(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/verifications/github/start — Start GitHub OAuth."""
    verification, state = await verification_service.start_github_verification(
        db, current_agent,
    )
    return {
        "verification_id": verification.id,
        "status": "pending",
        "message": "GitHub OAuth flow initiated",
        "_dev_state": state,
    }


@router.post("/domain/start", status_code=201)
async def start_domain_verification(
    domain: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/verifications/domain/start — DNS TXT verification."""
    verification, txt_value = await verification_service.start_domain_verification(
        db, current_agent, domain,
    )
    return {
        "verification_id": verification.id,
        "domain": domain,
        "dns_record_type": "TXT",
        "dns_record_name": f"_seabay.{domain}",
        "dns_record_value": txt_value,
        "status": "pending",
    }


@router.post("/domain/complete")
async def complete_domain_verification(
    verification_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/verifications/domain/complete — Confirm DNS record."""
    verification = await verification_service.complete_domain_verification(
        db, current_agent, verification_id,
    )
    return {"verification_id": verification.id, "status": "verified"}


@router.post("/workspace/start", status_code=201)
async def start_workspace_verification(
    workspace_domain: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/verifications/workspace/start — Start workspace domain verification."""
    verification, txt_value = await verification_service.start_workspace_verification(
        db, current_agent.id, workspace_domain,
    )
    return {
        "verification_id": verification.id,
        "workspace_domain": workspace_domain,
        "dns_record_type": "TXT",
        "dns_record_name": f"_seabay-workspace.{workspace_domain}",
        "dns_record_value": txt_value,
        "status": "pending",
    }


@router.post("/workspace/complete")
async def complete_workspace_verification(
    verification_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/verifications/workspace/complete — Confirm workspace DNS record."""
    verification = await verification_service.complete_workspace_verification(
        db, current_agent.id, verification_id,
    )
    return {"verification_id": verification.id, "status": "verified"}


@router.get("/my")
async def list_my_verifications(
    method: str | None = None,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/verifications/my — List current agent's verifications."""
    verifications = await verification_service.get_verifications(
        db, current_agent.id, method=method,
    )
    return {
        "data": [
            {
                "id": v.id,
                "method": v.method,
                "status": v.status,
                "identifier": v.identifier,
                "verified_at": v.verified_at,
                "created_at": v.created_at,
            }
            for v in verifications
        ],
    }
