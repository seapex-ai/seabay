"""Webhook configuration service — agent webhook endpoint management.

Manages agent webhook endpoints and delivery preferences.
Each agent can configure:
- Webhook URL (endpoint in Agent model)
- Webhook secret for HMAC signing
- Event type subscriptions
- Delivery preferences (retry count, timeout)

V1.5: Configuration stored in agent endpoint + in-memory preferences.
V1.6+: Dedicated webhook_configs table with per-event settings.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRequestError
from app.models.agent import Agent

logger = logging.getLogger(__name__)

# Default webhook settings
DEFAULT_TIMEOUT = 10.0  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAYS = [0, 1, 5, 25]  # seconds

# Allowed event types for webhook subscriptions
WEBHOOK_EVENT_TYPES = {
    "task.created",
    "task.accepted",
    "task.declined",
    "task.completed",
    "task.cancelled",
    "task.failed",
    "task.expired",
    "task.human_confirm_required",
    "introduction.received",
    "introduction.accepted",
    "introduction.declined",
    "introduction.expired",
    "circle.join_request",
    "circle.member_joined",
    "circle.member_left",
    "report.received",
}

# In-memory webhook configs (V1.5)
_webhook_configs: dict[str, dict] = {}


async def configure_webhook(
    db: AsyncSession,
    agent: Agent,
    endpoint: str,
    secret: Optional[str] = None,
    events: Optional[list[str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict:
    """Configure webhook endpoint for an agent.

    Args:
        agent: The agent to configure
        endpoint: The webhook URL (must be HTTPS in production)
        secret: Optional HMAC signing secret
        events: List of event types to subscribe to (None = all)
        timeout: Webhook delivery timeout in seconds
        max_retries: Maximum number of retry attempts
    """
    # Validate endpoint URL
    if not endpoint.startswith("https://") and not endpoint.startswith("http://localhost"):
        raise InvalidRequestError(
            "Webhook endpoint must use HTTPS (http://localhost allowed for development)"
        )

    # Validate event types
    if events:
        invalid = set(events) - WEBHOOK_EVENT_TYPES
        if invalid:
            raise InvalidRequestError(
                f"Invalid event types: {', '.join(sorted(invalid))}"
            )

    # Update agent endpoint
    agent.endpoint = endpoint
    await db.flush()

    # Store configuration in memory
    config = {
        "agent_id": agent.id,
        "endpoint": endpoint,
        "secret": secret,
        "events": events or list(WEBHOOK_EVENT_TYPES),
        "timeout": min(timeout, 30.0),
        "max_retries": min(max_retries, 5),
        "retry_delays": DEFAULT_RETRY_DELAYS[:max_retries + 1],
    }
    _webhook_configs[agent.id] = config

    logger.info(
        "Webhook configured for agent %s: %s (%d events)",
        agent.id, endpoint, len(config["events"]),
    )
    return config


def get_webhook_config(agent_id: str) -> Optional[dict]:
    """Get webhook configuration for an agent."""
    return _webhook_configs.get(agent_id)


def should_deliver(agent_id: str, event_type: str) -> bool:
    """Check if a webhook should be delivered for a given event type."""
    config = _webhook_configs.get(agent_id)
    if not config:
        return True  # No config = deliver all events

    return event_type in config.get("events", [])


async def remove_webhook(
    db: AsyncSession,
    agent: Agent,
) -> None:
    """Remove webhook configuration for an agent."""
    agent.endpoint = None
    await db.flush()
    _webhook_configs.pop(agent.id, None)
    logger.info("Webhook removed for agent %s", agent.id)


async def test_webhook(
    agent: Agent,
) -> dict:
    """Send a test webhook to the agent's configured endpoint.

    Returns delivery result.
    """
    if not agent.endpoint:
        raise InvalidRequestError("No webhook endpoint configured")

    from app.services.webhook_service import deliver_webhook

    success, status_code, error = await deliver_webhook(
        endpoint=agent.endpoint,
        event="webhook.test",
        payload={"message": "Webhook test from Seabay", "agent_id": agent.id},
        secret=_webhook_configs.get(agent.id, {}).get("secret"),
    )

    return {
        "success": success,
        "status_code": status_code,
        "error": error,
        "endpoint": agent.endpoint,
    }


def list_event_types() -> list[str]:
    """List all available webhook event types."""
    return sorted(WEBHOOK_EVENT_TYPES)
