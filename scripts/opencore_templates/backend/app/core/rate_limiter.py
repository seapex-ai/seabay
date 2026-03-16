"""Rate limiting middleware for open-core builds.

Open-core does not ship production anti-abuse thresholds. If no limits are
configured, this middleware becomes a no-op. Self-hosted operators can set
their own values through environment variables.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

logger = logging.getLogger(__name__)

RATE_LIMITS = {
    "POST:/v1/agents/register": (settings.RATE_LIMIT_REGISTER, 3600),
    "GET:/v1/agents/search": (settings.RATE_LIMIT_SEARCH, 60),
    "POST:default": (settings.RATE_LIMIT_POST, 60),
    "GET:default": (settings.RATE_LIMIT_READ, 60),
    "GET:/v1/public": (settings.RATE_LIMIT_PUBLIC, 60),
}

_redis_client: Optional[object] = None


async def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True,
            )
            await _redis_client.ping()
        except Exception:
            logger.warning("Redis not available — rate limiting disabled")
            _redis_client = False  # type: ignore[assignment]
    return _redis_client if _redis_client is not False else None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        redis = await _get_redis()
        if not redis:
            return await call_next(request)

        method = request.method
        path = request.url.path
        limit, window = self._get_limit(method, path)
        if limit is None or limit <= 0:
            return await call_next(request)

        api_key = request.headers.get("authorization", "")
        if api_key.startswith("Bearer "):
            identifier = f"key:{api_key[7:20]}"
        else:
            identifier = f"ip:{request.client.host if request.client else 'unknown'}"

        rate_key = f"rl:{identifier}:{method}:{path}"

        try:
            current = await redis.incr(rate_key)
            if current == 1:
                await redis.expire(rate_key, window)

            if current > limit:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "rate_limited",
                            "message": "Too many requests",
                            "details": {},
                        }
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(window),
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
            return response
        except Exception:
            logger.warning("Rate limit check failed", exc_info=True)
            return await call_next(request)

    def _get_limit(self, method: str, path: str) -> tuple:
        route_key = f"{method}:{path}"
        if route_key in RATE_LIMITS:
            return RATE_LIMITS[route_key]

        if path.startswith("/v1/public"):
            return RATE_LIMITS.get("GET:/v1/public", (None, None))

        default_key = f"{method}:default"
        if default_key in RATE_LIMITS:
            return RATE_LIMITS[default_key]

        return (None, None)
