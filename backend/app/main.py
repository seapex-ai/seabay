"""Seabay — FastAPI Application Entry Point."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_v1_router
from app.config import settings
from app.core.middleware import RequestIdMiddleware
from app.core.rate_limiter import RateLimitMiddleware

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("seabay")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — start/stop background workers."""
    shutdown_event = asyncio.Event()
    worker_tasks = []

    # Start background workers
    from app.workers.metrics_aggregator import run_metrics_aggregator
    from app.workers.payload_cleaner import run_payload_cleaner
    from app.workers.status_decay import run_status_decay
    from app.workers.strength_deriver import run_strength_deriver
    from app.workers.task_delivery import run_delivery_worker
    from app.workers.ttl_checker import run_ttl_checker

    worker_tasks.append(asyncio.create_task(run_delivery_worker(shutdown_event)))
    worker_tasks.append(asyncio.create_task(run_ttl_checker(shutdown_event)))
    worker_tasks.append(asyncio.create_task(run_status_decay(shutdown_event)))
    worker_tasks.append(asyncio.create_task(run_strength_deriver(shutdown_event)))
    worker_tasks.append(asyncio.create_task(run_metrics_aggregator(shutdown_event)))
    worker_tasks.append(asyncio.create_task(run_payload_cleaner(shutdown_event)))

    # Production safety checks
    if not settings.DEBUG:
        if settings.PASSPORT_SIGNING_KEY == "DO-NOT-USE-IN-PRODUCTION-dev-only":
            logger.warning("SEABAY_PASSPORT_SIGNING_KEY is using dev default — set a secure key for production")
        if settings.CORS_ORIGINS == "*":
            logger.warning("SEABAY_CORS_ORIGINS is set to '*' — restrict to specific domains in production")

    logger.info(
        "Seabay %s started (region=%s, workers=%d)",
        settings.APP_VERSION, settings.REGION, len(worker_tasks),
    )
    yield

    # Shutdown workers gracefully
    logger.info("Shutting down background workers...")
    shutdown_event.set()
    await asyncio.gather(*worker_tasks, return_exceptions=True)
    logger.info("All workers stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Networked collaboration ability layer for AI Agents",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    servers=[
        {"url": "https://api.seabay.ai", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
)

# Middleware (order matters: last added = first executed)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 routes
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


# ── Global Exception Handler ──

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return structured error response."""
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
                "details": {"path": request.url.path}
                if settings.DEBUG else {},
            }
        },
    )


# ── Request Logging Middleware ──

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request method, path, status, and duration."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000

    if request.url.path not in ("/v1/health", "/docs", "/redoc", "/openapi.json"):
        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    return response


# A2A well-known endpoint (outside /v1 prefix)
@app.get("/.well-known/agent-card/{agent_id}.json", tags=["a2a"])
async def well_known_agent_card(agent_id: str):
    """A2A-compatible agent card output."""
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.agent import Agent, Profile

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent, Profile)
            .outerjoin(Profile, Profile.agent_id == Agent.id)
            .where(
                Agent.id == agent_id,
                Agent.visibility_scope == "public",
                Agent.status.notin_(["suspended", "banned"]),
            )
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")

        agent = row.Agent
        profile = row.Profile

        return {
            "id": agent.id,
            "name": agent.display_name,
            "description": profile.bio if profile else None,
            "url": f"https://seabay.ai/agents/{agent.slug}",
            "provider": {"organization": "Seabay", "url": "https://seabay.ai"},
            "version": "1.0",
            "capabilities": {
                "skills": profile.skills if profile else [],
                "languages": profile.languages if profile else [],
            },
            "authentication": {"schemes": ["bearer"]},
            "defaultInputModes": ["application/json"],
            "defaultOutputModes": ["application/json"],
        }
