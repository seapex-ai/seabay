"""SSE event stream — real-time push notifications.

GET /v1/events/stream — SSE endpoint for receiving real-time events.
GET /v1/events/status — Connection status.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_agent
from app.database import get_db
from app.models.agent import Agent
from app.services import notification_service

router = APIRouter()


@router.get("/stream")
async def event_stream(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/events/stream — SSE stream for real-time notifications.

    Events:
    - task.created, task.accepted, task.completed, task.declined, task.cancelled
    - introduction.pending, introduction.accepted, introduction.declined
    - circle.joined, circle.join_request

    Headers:
    - Authorization: Bearer {api_key}
    - Accept: text/event-stream
    """
    return StreamingResponse(
        notification_service.subscribe(current_agent.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: disable buffering
        },
    )


@router.get("/status")
async def event_status(
    current_agent: Agent = Depends(get_current_agent),
):
    """GET /v1/events/status — Check SSE connection status."""
    return {
        "agent_id": current_agent.id,
        "active_connections": notification_service.get_connection_count(current_agent.id),
        "is_connected": notification_service.get_connection_count(current_agent.id) > 0,
    }
