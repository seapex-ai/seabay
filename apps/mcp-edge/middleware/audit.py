"""Audit trace wrapper for MCP tool invocations.

Logs every tool invocation with:
- Timestamp
- User/subject (from OAuth token)
- Tool name
- Parameters (sanitized)
- Result status
- Trace ID for correlation

Per spec section 13, decision #11: every tool invocation carries a trace_id
and is recorded to interaction_log for V2 Reputation data preparation.
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings

logger = logging.getLogger("mcp-edge.audit")

# Fields to redact from audit logs
_REDACT_FIELDS = frozenset({
    "api_key", "token", "secret", "password", "authorization",
    "access_token", "refresh_token", "code_verifier",
})


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every request with a trace ID.

    Adds X-Trace-Id header to responses for correlation.
    Logs tool invocations to the audit trail.
    """

    async def dispatch(self, request: Request, call_next):
        # Generate trace ID
        trace_id = f"trc_{secrets.token_urlsafe(16)}"
        request.state.trace_id = trace_id

        # Extract user info from token if available
        subject = "anonymous"
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Just note that auth is present; actual validation happens in deps
            subject = "authenticated"

        start_time = time.monotonic()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Trace-Id"] = trace_id
            return response
        except Exception as exc:
            logger.error(
                "Request failed: trace_id=%s path=%s error=%s",
                trace_id, request.url.path, exc,
            )
            raise
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000

            # Log audit entry for tool invocations
            if request.url.path.startswith("/tools/"):
                tool_name = request.url.path.split("/tools/")[-1].split("/")[0]
                _log_tool_invocation(
                    trace_id=trace_id,
                    tool_name=tool_name,
                    subject=subject,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                )


def _log_tool_invocation(
    trace_id: str,
    tool_name: str,
    subject: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Log a tool invocation to the audit trail.

    In V1.0, this logs to structured logger. In production, this would
    write to the interaction_log table via Core API.
    """
    if not settings.AUDIT_LOG_ENABLED:
        return

    logger.info(
        "AUDIT tool=%s subject=%s status=%d duration=%.1fms trace_id=%s",
        tool_name,
        subject,
        status_code,
        duration_ms,
        trace_id,
    )


def create_audit_entry(
    trace_id: str,
    tool_name: str,
    subject: str,
    params: dict,
    result_status: str,
    error: Optional[str] = None,
) -> dict:
    """Create a structured audit entry for storage.

    Args:
        trace_id: Request trace ID
        tool_name: Name of the MCP tool
        subject: OAuth subject or "anonymous"
        params: Tool parameters (will be sanitized)
        result_status: "success", "error", "blocked"
        error: Error message if any

    Returns:
        Structured audit entry dict
    """
    sanitized_params = _sanitize_params(params)

    entry = {
        "trace_id": trace_id,
        "tool_name": tool_name,
        "subject": subject,
        "params": sanitized_params,
        "result_status": result_status,
        "timestamp": time.time(),
    }

    if error:
        entry["error"] = error

    return entry


def _sanitize_params(params: dict) -> dict:
    """Remove sensitive fields from parameters before logging."""
    sanitized = {}
    for key, value in params.items():
        if key.lower() in _REDACT_FIELDS:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_params(value)
        else:
            sanitized[key] = value
    return sanitized
