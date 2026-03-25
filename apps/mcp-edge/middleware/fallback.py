"""Fallback URL broker for non-MCP clients.

Generates web fallback URLs for all tool responses. When the MCP host
cannot render structured data (or for R2/R3 approval flows), users
can click the fallback URL to complete the action on the Seabay web app.

Per spec section 9.1: V1.0 uses pure text + fallback URL. No inline widgets.
Per spec section 6.2: All R2/R3 flows have a web URL fallback.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter

from config import settings

logger = logging.getLogger("mcp-edge.fallback")

router = APIRouter()

# Base URL for the Seabay web application
_BASE_URL = settings.FALLBACK_BASE_URL


@router.get("/search")
async def fallback_search(
    skills: str | None = None,
    location: str | None = None,
    language: str | None = None,
):
    """Generate a fallback search URL and redirect info.

    Used when an MCP host cannot directly render search results.
    """
    url = build_search_url(skills=skills, location=location, language=language)
    return {
        "fallback_url": url,
        "message": "Open this URL to search for agents on the Seabay web app.",
    }


@router.get("/agent/{agent_id}")
async def fallback_agent_profile(agent_id: str):
    """Generate a fallback URL for viewing an agent profile."""
    url = build_agent_url(agent_id)
    return {
        "fallback_url": url,
        "message": "Open this URL to view the agent profile on Seabay.",
    }


@router.get("/task/{task_id}")
async def fallback_task(task_id: str):
    """Generate a fallback URL for viewing a task."""
    url = build_task_url(task_id)
    return {
        "fallback_url": url,
        "message": "Open this URL to view the task details on Seabay.",
    }


@router.get("/approval/{approval_id}")
async def fallback_approval(approval_id: str):
    """Generate a fallback URL for an approval flow.

    Used for R2/R3 human confirmation when the MCP host doesn't
    support inline approval (or the conversation is interrupted).
    """
    url = build_approval_url(approval_id)
    return {
        "fallback_url": url,
        "message": (
            "This action requires your confirmation. "
            "Open this URL to approve or reject on the Seabay web app."
        ),
    }


@router.get("/inbox")
async def fallback_inbox():
    """Generate a fallback URL for the inbox."""
    return {
        "fallback_url": f"{_BASE_URL}/inbox",
        "message": "Open this URL to view your inbox on Seabay.",
    }


# ── URL Builder Functions ──

def build_search_url(
    skills: str | None = None,
    location: str | None = None,
    language: str | None = None,
) -> str:
    """Build a web search URL with query parameters."""
    params = {}
    if skills:
        params["skills"] = skills
    if location:
        params["location"] = location
    if language:
        params["language"] = language

    base = f"{_BASE_URL}/search"
    if params:
        return f"{base}?{urlencode(params)}"
    return base


def build_agent_url(agent_id: str) -> str:
    """Build a web URL for an agent profile."""
    return f"{_BASE_URL}/agents/{agent_id}"


def build_task_url(task_id: str) -> str:
    """Build a web URL for a task detail page."""
    return f"{_BASE_URL}/tasks/{task_id}"


def build_approval_url(approval_id: str) -> str:
    """Build a web URL for an approval confirmation page."""
    return f"{_BASE_URL}/approvals/{approval_id}"


def build_inbox_url() -> str:
    """Build a web URL for the inbox."""
    return f"{_BASE_URL}/inbox"
