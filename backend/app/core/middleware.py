"""Middleware: request ID, trace ID, region header, CORS."""

from __future__ import annotations

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.core.id_generator import generate_id

# Context variable for trace_id — accessible from any service layer
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))

        # Propagate or generate X-Trace-Id for cross-platform correlation
        trace_id = request.headers.get("X-Trace-Id") or generate_id("trc")
        trace_id_var.set(trace_id)

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Region"] = settings.REGION
        return response
