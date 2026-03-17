"""Notification service — in-memory event bus for SSE push.

Provides real-time push notifications to connected agents via SSE.
Events: task.created, task.accepted, task.completed, task.declined,
        task.cancelled, introduction.received, introduction.accepted,
        circle.joined, circle.join_request, report.received.

Architecture:
- In-memory asyncio.Queue per connected agent (scales to single node)
- For multi-node: plug in Redis pub/sub (V1.6)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# Agent ID → set of queues (one agent can have multiple SSE connections)
_subscriptions: dict[str, set[asyncio.Queue]] = {}


async def subscribe(agent_id: str) -> AsyncIterator[str]:
    """Subscribe to events for an agent. Yields SSE-formatted strings.

    Usage in endpoint:
        async def sse_endpoint(...):
            return StreamingResponse(
                notification_service.subscribe(agent_id),
                media_type="text/event-stream",
            )
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    if agent_id not in _subscriptions:
        _subscriptions[agent_id] = set()
    _subscriptions[agent_id].add(queue)

    logger.info("SSE connected: agent=%s (total=%d)", agent_id, len(_subscriptions[agent_id]))

    try:
        # Send initial heartbeat
        yield _format_sse("connected", {"agent_id": agent_id, "ts": _now_iso()})

        while True:
            try:
                # Wait for event with timeout (heartbeat every 30s)
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield _format_sse("heartbeat", {"ts": _now_iso()})
    except asyncio.CancelledError:
        pass
    finally:
        _subscriptions.get(agent_id, set()).discard(queue)
        if agent_id in _subscriptions and not _subscriptions[agent_id]:
            del _subscriptions[agent_id]
        logger.info("SSE disconnected: agent=%s", agent_id)


async def push_event(
    agent_id: str,
    event_type: str,
    data: dict,
    event_id: Optional[str] = None,
) -> int:
    """Push an event to all SSE connections for an agent.

    Returns number of connections that received the event.
    """
    queues = _subscriptions.get(agent_id, set())
    if not queues:
        return 0

    formatted = _format_sse(event_type, data, event_id)
    delivered = 0

    for queue in list(queues):
        try:
            queue.put_nowait(formatted)
            delivered += 1
        except asyncio.QueueFull:
            logger.warning(
                "SSE queue full for agent=%s, dropping event=%s",
                agent_id, event_type,
            )

    return delivered


async def notify_task_event(
    agent_id: str,
    event_type: str,
    task_id: str,
    from_agent_id: str,
    task_type: str,
    status: str,
    description: Optional[str] = None,
) -> int:
    """Push a task lifecycle event."""
    return await push_event(agent_id, event_type, {
        "task_id": task_id,
        "from_agent_id": from_agent_id,
        "task_type": task_type,
        "status": status,
        "description": description,
        "ts": _now_iso(),
    }, event_id=task_id)


async def notify_introduction(
    agent_id: str,
    introduction_id: str,
    introducer_id: str,
    other_agent_id: str,
    reason: Optional[str] = None,
    status: str = "pending",
) -> int:
    """Push an introduction event."""
    return await push_event(agent_id, f"introduction.{status}", {
        "introduction_id": introduction_id,
        "introducer_id": introducer_id,
        "other_agent_id": other_agent_id,
        "reason": reason,
        "status": status,
        "ts": _now_iso(),
    }, event_id=introduction_id)


async def notify_circle_event(
    agent_id: str,
    event_type: str,
    circle_id: str,
    circle_name: str,
    actor_agent_id: Optional[str] = None,
) -> int:
    """Push a circle event (join, leave, request)."""
    return await push_event(agent_id, event_type, {
        "circle_id": circle_id,
        "circle_name": circle_name,
        "actor_agent_id": actor_agent_id,
        "ts": _now_iso(),
    }, event_id=circle_id)


def get_connected_agents() -> list[str]:
    """Return list of agent IDs with active SSE connections."""
    return list(_subscriptions.keys())


def get_connection_count(agent_id: str) -> int:
    """Return number of active SSE connections for an agent."""
    return len(_subscriptions.get(agent_id, set()))


# ── Formatters ──

def _format_sse(
    event_type: str,
    data: dict,
    event_id: Optional[str] = None,
) -> str:
    """Format data as SSE message."""
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    lines.append("")  # blank line terminates event
    return "\n".join(lines) + "\n"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
