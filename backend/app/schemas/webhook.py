"""Webhook configuration and delivery schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WebhookConfigRequest(BaseModel):
    """Request to configure a webhook endpoint."""
    endpoint: str = Field(
        ...,
        description="Webhook URL (must be HTTPS, http://localhost for dev)",
    )
    secret: str | None = Field(
        None,
        description="HMAC signing secret for payload verification",
    )
    events: list[str] | None = Field(
        None,
        description="Event types to subscribe to (None = all)",
    )
    timeout: float = Field(
        10.0,
        ge=1.0,
        le=30.0,
        description="Delivery timeout in seconds",
    )
    max_retries: int = Field(
        3,
        ge=0,
        le=5,
        description="Maximum retry attempts",
    )


class WebhookConfigResponse(BaseModel):
    """Webhook configuration details."""
    agent_id: str
    endpoint: str
    events: list[str]
    timeout: float
    max_retries: int
    retry_delays: list[int]


class WebhookTestResponse(BaseModel):
    """Result of a webhook test delivery."""
    success: bool
    status_code: int
    error: str | None = None
    endpoint: str


class WebhookDeliveryRecord(BaseModel):
    """Record of a webhook delivery attempt."""
    event_type: str
    endpoint: str
    status_code: int
    success: bool
    error: str | None = None
    attempt: int
    delivered_at: datetime


class WebhookEventList(BaseModel):
    """Available webhook event types."""
    events: list[str]
