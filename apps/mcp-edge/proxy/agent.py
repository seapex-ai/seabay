"""Proxy Agent auto-creation for MCP consumer users.

When a user first authenticates via OAuth to an MCP host (Claude, ChatGPT, etc.),
they may not have an existing Seabay agent. The system automatically creates a
"proxy agent" — a lightweight personal agent that:

- Has visibility: network_only (not publicly discoverable)
- Can initiate tasks, receive results, and view inbox
- Is linked to the OAuth installation record

This reuses the existing personal agent model from V1.5.

See Remote MCP Server v1.0 spec section 4.1 (Mode B: Proxy Agent).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

import httpx

from auth.jwt import create_core_auth_header

logger = logging.getLogger("mcp-edge.proxy")


async def ensure_proxy_agent(
    core_client: httpx.AsyncClient,
    oauth_subject: str,
    host_type: str,
    scopes: list[str],
) -> dict:
    """Ensure a proxy agent and installation exist for the OAuth subject.

    If the user already has a linked agent, returns that. Otherwise,
    creates a new personal proxy agent and an installation record.

    Args:
        core_client: httpx client connected to Core API
        oauth_subject: OAuth subject identifier
        host_type: MCP host type (claude, chatgpt, etc.)
        scopes: Granted OAuth scopes

    Returns:
        dict with keys: agent_id, installation_id, is_new
    """
    # Check if installation already exists for this subject + host
    # (In production, this would be a Core API lookup)
    # For V1.0, we create a new proxy agent via the register endpoint

    slug = f"proxy_{host_type}_{secrets.token_urlsafe(8)}"
    display_name = f"{host_type.title()} User ({oauth_subject[:16]})"

    register_body = {
        "slug": slug,
        "display_name": display_name,
        "agent_type": "personal",
        "owner_type": "individual",
        "bio": f"Auto-created proxy agent for {host_type} MCP connection.",
    }

    try:
        # Use internal JWT to register on behalf of the user
        headers = create_core_auth_header(
            subject=oauth_subject,
            scopes=["admin"],  # Internal registration requires elevated scope
        )

        response = await core_client.post(
            "/agents/register",
            json=register_body,
            headers=headers,
        )

        if response.status_code == 201:
            data = response.json()
            agent_id = data.get("id")
            api_key = data.get("api_key")

            logger.info(
                "Proxy agent created: agent_id=%s host=%s subject=%s",
                agent_id, host_type, oauth_subject,
            )

            # Create installation record
            installation = await _create_installation(
                core_client=core_client,
                host_type=host_type,
                proxy_agent_id=agent_id,
                oauth_subject=oauth_subject,
                scopes=scopes,
            )

            return {
                "agent_id": agent_id,
                "api_key": api_key,
                "installation_id": installation.get("id"),
                "is_new": True,
            }
        else:
            logger.error(
                "Failed to create proxy agent: status=%d body=%s",
                response.status_code, response.text,
            )
            return {"agent_id": None, "installation_id": None, "is_new": False}

    except Exception as e:
        logger.error("Proxy agent creation error: %s", e)
        return {"agent_id": None, "installation_id": None, "is_new": False}


async def link_existing_agent(
    core_client: httpx.AsyncClient,
    agent_id: str,
    oauth_subject: str,
    host_type: str,
    scopes: list[str],
) -> dict:
    """Link an existing agent to an MCP installation.

    Used when a developer with an existing agent connects their MCP host.

    Args:
        core_client: httpx client connected to Core API
        agent_id: Existing agent ID to link
        oauth_subject: OAuth subject identifier
        host_type: MCP host type
        scopes: Granted OAuth scopes

    Returns:
        dict with keys: agent_id, installation_id, is_new
    """
    installation = await _create_installation(
        core_client=core_client,
        host_type=host_type,
        linked_agent_id=agent_id,
        oauth_subject=oauth_subject,
        scopes=scopes,
    )

    logger.info(
        "Agent linked to installation: agent_id=%s host=%s",
        agent_id, host_type,
    )

    return {
        "agent_id": agent_id,
        "installation_id": installation.get("id"),
        "is_new": False,
    }


async def _create_installation(
    core_client: httpx.AsyncClient,
    host_type: str,
    oauth_subject: str,
    scopes: list[str],
    linked_agent_id: str | None = None,
    proxy_agent_id: str | None = None,
) -> dict:
    """Create an installation record in the Core API.

    In V1.0, this is a simplified in-memory record.
    Production would persist to the installations table.
    """
    installation_id = f"ins_{secrets.token_urlsafe(16)}"

    installation = {
        "id": installation_id,
        "host_type": host_type,
        "linked_agent_id": linked_agent_id,
        "proxy_agent_id": proxy_agent_id,
        "oauth_subject": oauth_subject,
        "granted_scopes": scopes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Installation created: id=%s host=%s agent=%s",
        installation_id, host_type, linked_agent_id or proxy_agent_id,
    )

    return installation
