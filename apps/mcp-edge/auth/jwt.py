"""Internal JWT signing for Edge -> Core communication.

The MCP Edge layer uses short-lived signed JWTs when calling the
Core API on behalf of authenticated MCP users. This avoids token
passthrough (Frozen Principle #3 from the V1.5 spec).

The Core API validates these JWTs to trust the Edge's assertions
about the caller's identity and scopes.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from jose import JWTError, jwt

from config import settings

logger = logging.getLogger("mcp-edge.jwt")


def create_internal_jwt(
    subject: str,
    scopes: list[str],
    installation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> str:
    """Create a short-lived internal JWT for Edge -> Core API calls.

    Args:
        subject: OAuth subject identifier (user/client ID)
        scopes: Granted OAuth scopes
        installation_id: Installation record ID
        agent_id: The effective agent_id (linked or proxy)

    Returns:
        Signed JWT string
    """
    now = int(time.time())
    payload = {
        "iss": "mcp-edge",
        "sub": subject,
        "aud": "seabay-core",
        "iat": now,
        "exp": now + settings.JWT_TTL,
        "scopes": scopes,
    }
    if installation_id:
        payload["installation_id"] = installation_id
    if agent_id:
        payload["agent_id"] = agent_id

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def verify_internal_jwt(token: str) -> dict:
    """Verify and decode an internal JWT.

    Args:
        token: The JWT string to verify

    Returns:
        Decoded payload dict

    Raises:
        ValueError: If the token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience="seabay-core",
            issuer="mcp-edge",
        )
        return payload
    except JWTError as e:
        logger.warning("Internal JWT verification failed: %s", e)
        raise ValueError(f"Invalid internal JWT: {e}") from e


def create_core_auth_header(
    subject: str,
    scopes: list[str],
    installation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> dict[str, str]:
    """Create HTTP headers for authenticated Core API calls.

    Returns a dict with Authorization header containing the internal JWT.
    """
    token = create_internal_jwt(
        subject=subject,
        scopes=scopes,
        installation_id=installation_id,
        agent_id=agent_id,
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Edge-Version": settings.APP_VERSION,
        "X-Request-Source": "mcp-edge",
    }
