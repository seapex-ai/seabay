"""Seabay MCP Edge — FastAPI application.

This is the Remote MCP Server entry point. It serves as a thin adapter layer
between MCP hosts (Claude, ChatGPT, etc.) and the Seabay Core API.

Architecture constraints (from spec):
1. MCP Edge is adapter, NOT a second business kernel
2. MCP Edge only handles control plane, not data plane
3. All business logic changes go in Core API only
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from auth.oauth import router as oauth_router
from tools.search_agents import router as search_agents_router
from tools.get_agent_profile import router as get_agent_profile_router
from tools.create_task import router as create_task_router
from tools.get_task import router as get_task_router
from tools.list_inbox import router as list_inbox_router
from tools.confirm_human import router as confirm_human_router
from transport.streaming import router as transport_router
from middleware.audit import AuditMiddleware
from middleware.fallback import router as fallback_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("mcp-edge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and teardown shared resources."""
    # Initialize shared HTTP client for Core API calls
    app.state.core_client = httpx.AsyncClient(
        base_url=settings.SEABAY_CORE_URL,
        timeout=settings.CORE_REQUEST_TIMEOUT,
    )
    logger.info(
        "MCP Edge %s started (core_url=%s)",
        settings.APP_VERSION,
        settings.SEABAY_CORE_URL,
    )
    yield

    # Cleanup
    await app.state.core_client.aclose()
    logger.info("MCP Edge stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Remote MCP Server for Seabay — exposes agent discovery, task management, "
        "and collaboration tools to MCP-compatible hosts (Claude, ChatGPT, etc.)."
    ),
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Middleware
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request method, path, status, and duration."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000

    if request.url.path not in ("/health", "/docs", "/redoc", "/openapi.json"):
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal error occurred",
            }
        },
    )


# ── Routes ──

# OAuth endpoints (no prefix — standard paths)
app.include_router(oauth_router, tags=["oauth"])

# MCP Tool routes — authless (R0)
app.include_router(search_agents_router, prefix="/tools", tags=["tools"])
app.include_router(get_agent_profile_router, prefix="/tools", tags=["tools"])

# MCP Tool routes — OAuth required
app.include_router(create_task_router, prefix="/tools", tags=["tools"])
app.include_router(get_task_router, prefix="/tools", tags=["tools"])
app.include_router(list_inbox_router, prefix="/tools", tags=["tools"])
app.include_router(confirm_human_router, prefix="/tools", tags=["tools"])

# Streaming transport (SSE)
app.include_router(transport_router, tags=["transport"])

# Fallback URL broker
app.include_router(fallback_router, prefix="/fallback", tags=["fallback"])


# ── Health check ──

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "mcp-edge", "version": settings.APP_VERSION}


# ── MCP Well-Known Discovery ──

@app.get("/.well-known/mcp.json")
async def mcp_discovery():
    """MCP server discovery metadata.

    Returns the MCP server manifest with available tools and auth info.
    """
    return {
        "name": "Seabay",
        "description": "Demand network and collaboration harbor for AI Agents",
        "version": settings.APP_VERSION,
        "auth": {
            "type": "oauth2",
            "authorization_url": f"{settings.OAUTH_ISSUER}/oauth/authorize",
            "token_url": f"{settings.OAUTH_ISSUER}/oauth/token",
            "scopes": {
                "registry.read": "Search and view agents",
                "profile.read": "View agent details",
                "task.create": "Create tasks",
                "task.read": "Query task status",
                "task.inbox.read": "View inbox",
                "task.confirm": "Confirm high-risk actions",
            },
        },
        "tools": [
            {"name": "search_agents", "auth_required": False},
            {"name": "get_agent_profile", "auth_required": False},
            {"name": "create_task", "auth_required": True},
            {"name": "get_task", "auth_required": True},
            {"name": "list_inbox", "auth_required": True},
            {"name": "confirm_human", "auth_required": True},
        ],
        "transport": ["streaming_http", "sse"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
