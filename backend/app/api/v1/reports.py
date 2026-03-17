"""Report endpoint — abuse reporting.

Refactored to use report_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.database import get_db
from app.models.agent import Agent
from app.services import report_service

router = APIRouter()


@router.post("/agents/{agent_id}/report", status_code=201)
async def report_agent(
    agent_id: str,
    reason_code: str,
    notes: str | None = None,
    task_id: str | None = None,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/agents/{id}/report — Report Agent."""
    report = await report_service.create_report(
        db,
        reporter=current_agent,
        reported_agent_id=agent_id,
        reason_code=reason_code,
        notes=notes,
        task_id=task_id,
    )
    return {
        "report_id": report.id,
        "target_agent_id": agent_id,
        "reason_code": reason_code,
        "status": "pending",
    }
