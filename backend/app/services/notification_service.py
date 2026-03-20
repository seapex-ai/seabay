"""Notification service — SSE push with Redis pub/sub for multi-node support.

V1.6: Replaced in-memory queues with Redis pub/sub channels.
Each API instance subscribes to Redis channels per agent_id, so SSE events
are delivered regardless of which node the client is connected to.

Fallback: When Redis is unavailable (e.g. in tests or single-node dev),
automatically falls back to in-memory asyncio.Queue-based delivery.

Events: task.created, task.accepted, task.completed, task.declined,
        task.cancelled, introduction.received, introduction.accepted,
        circle.joined, circle.join_request, report.received.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# ── Redis support (optional) ──
try:
    import redis.asyncio as aioredis
    _HAS_REDIS_LIB = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    _HAS_REDIS_LIB = False

# Redis channel prefix for SSE events
_CHANNEL_PREFIX = "seabay:sse:"

# Lazy-initialized Redis connection pool (None = not yet attempted)
_redis_pool: Optional[object] = None
_redis_available: Optional[bool] = None  # None = not tested yet

# Local tracking of active SSE connections per agent (for status endpoint)
_local_connections: dict[str, int] = {}

# ── In-memory fallback structures ──
_in_memory_queues: dict[str, list[asyncio.Queue]] = defaultdict(list)


async def _get_redis():
    """Get or create the shared Redis connection. Returns None if unavailable."""
    global _redis_pool, _redis_available

    if _redis_available is False:
        return None

    if not _HAS_REDIS_LIB:
        _redis_available = False
        return None

    if _redis_pool is not None:
        return _redis_pool

    try:
        from app.config import settings
        pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
        )
        # Verify connectivity with a ping
        await pool.ping()
        _redis_pool = pool
        _redis_available = True
        logger.info("Redis connected for SSE pub/sub")
        return _redis_pool
    except Exception:  # noqa: BLE001
        _redis_available = False
        logger.info("Redis unavailable — using in-memory SSE fallback")
        return None


def _channel_for(agent_id: str) -> str:
    """Return the Redis channel name for an agent."""
    return f"{_CHANNEL_PREFIX}{agent_id}"


# ── In-memory subscribe / push ──

async def _subscribe_in_memory(agent_id: str) -> AsyncIterator[str]:
    """In-memory subscription using asyncio.Queue (single-node fallback)."""
    queue: asyncio.Queue = asyncio.Queue()
    _in_memory_queues[agent_id].append(queue)
    _local_connections[agent_id] = _local_connections.get(agent_id, 0) + 1

    try:
        # Send initial heartbeat
        yield _format_sse("connected", {"agent_id": agent_id, "ts": _now_iso()})

        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield message
            except asyncio.TimeoutError:
                yield _format_sse("heartbeat", {"ts": _now_iso()})
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        if queue in _in_memory_queues.get(agent_id, []):
            _in_memory_queues[agent_id].remove(queue)
        if not _in_memory_queues.get(agent_id):
            _in_memory_queues.pop(agent_id, None)
        _local_connections[agent_id] = max(0, _local_connections.get(agent_id, 1) - 1)
        if _local_connections.get(agent_id, 0) == 0:
            _local_connections.pop(agent_id, None)


async def _push_in_memory(agent_id: str, formatted: str) -> int:
    """Push a formatted SSE message to all in-memory subscribers."""
    queues = _in_memory_queues.get(agent_id, [])
    count = 0
    for q in queues:
        await q.put(formatted)
        count += 1
    return count


# ── Redis subscribe / push ──

async def _subscribe_redis(agent_id: str) -> AsyncIterator[str]:
    """Subscribe via Redis pub/sub."""
    redis = await _get_redis()
    pubsub = redis.pubsub()
    channel = _channel_for(agent_id)

    await pubsub.subscribe(channel)
    _local_connections[agent_id] = _local_connections.get(agent_id, 0) + 1

    logger.info(
        "SSE connected via Redis: agent=%s channel=%s (local_conns=%d)",
        agent_id, channel, _local_connections[agent_id],
    )

    try:
        # Send initial heartbeat
        yield _format_sse("connected", {"agent_id": agent_id, "ts": _now_iso()})

        while True:
            try:
                # Poll Redis for messages with timeout (heartbeat every 30s)
                message = await asyncio.wait_for(
                    _read_next_message(pubsub), timeout=30.0,
                )
                if message is not None:
                    yield message
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield _format_sse("heartbeat", {"ts": _now_iso()})
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        _local_connections[agent_id] = max(0, _local_connections.get(agent_id, 1) - 1)
        if _local_connections.get(agent_id, 0) == 0:
            _local_connections.pop(agent_id, None)
        logger.info("SSE disconnected: agent=%s", agent_id)


async def _read_next_message(pubsub) -> Optional[str]:
    """Read the next message from pubsub, skipping subscribe confirmations."""
    while True:
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if msg is None:
            # No message available yet, let caller handle timeout
            await asyncio.sleep(0.1)
            return None
        if msg["type"] == "message":
            return msg["data"]


# ── Public API ──

async def subscribe(agent_id: str) -> AsyncIterator[str]:
    """Subscribe to events for an agent. Yields SSE-formatted strings.

    Uses Redis pub/sub when available, falls back to in-memory queues.

    Usage in endpoint:
        async def sse_endpoint(...):
            return StreamingResponse(
                notification_service.subscribe(agent_id),
                media_type="text/event-stream",
            )
    """
    redis = await _get_redis()
    if redis is not None:
        async for msg in _subscribe_redis(agent_id):
            yield msg
    else:
        async for msg in _subscribe_in_memory(agent_id):
            yield msg


async def push_event(
    agent_id: str,
    event_type: str,
    data: dict,
    event_id: Optional[str] = None,
) -> int:
    """Publish an event to all SSE connections for an agent.

    Uses Redis pub/sub when available, falls back to in-memory queues.
    Returns the number of subscribers that received the event, or 0 on failure.
    """
    formatted = _format_sse(event_type, data, event_id)

    redis = await _get_redis()
    if redis is not None:
        try:
            channel = _channel_for(agent_id)
            receivers = await redis.publish(channel, formatted)
            return receivers
        except Exception:  # noqa: BLE001
            logger.warning("Failed to publish SSE event to Redis for agent=%s", agent_id)
            return 0
    else:
        return await _push_in_memory(agent_id, formatted)


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
    """Return list of agent IDs with active SSE connections on this node."""
    return [aid for aid, count in _local_connections.items() if count > 0]


def get_connection_count(agent_id: str) -> int:
    """Return number of active SSE connections for an agent on this node."""
    return _local_connections.get(agent_id, 0)


async def close() -> None:
    """Close the Redis connection pool (for graceful shutdown)."""
    global _redis_pool, _redis_available
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
    _redis_available = None


def _reset_for_testing() -> None:
    """Reset all internal state (for tests only)."""
    global _redis_pool, _redis_available
    _redis_pool = None
    _redis_available = None
    _local_connections.clear()
    _in_memory_queues.clear()


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
