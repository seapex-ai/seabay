"""OAuth 2.1 Authorization Server for MCP Edge.

Implements the OAuth 2.1 flow for external MCP hosts (Claude, ChatGPT, etc.):
- POST /oauth/authorize — authorization endpoint (issues authorization codes)
- POST /oauth/token — token endpoint (exchanges codes for access tokens)

Token storage uses Redis for horizontal scalability.
Scopes: registry.read, profile.read, task.create, task.read,
        task.inbox.read, task.confirm.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger("mcp-edge.oauth")

router = APIRouter()

# ── In-memory stores (replaced by Redis in production) ──

# authorization_code -> {subject, scopes, redirect_uri, expires_at, code_challenge}
_auth_codes: dict[str, dict] = {}

# access_token_hash -> {subject, scopes, installation_id, expires_at}
_access_tokens: dict[str, dict] = {}

# refresh_token_hash -> {subject, scopes, installation_id, expires_at}
_refresh_tokens: dict[str, dict] = {}

# Valid scopes per MCP v1.0 spec section 7.3
VALID_SCOPES = frozenset({
    "registry.read",
    "profile.read",
    "task.create",
    "task.read",
    "task.inbox.read",
    "task.inbox.write",
    "task.confirm",
    "relationship.read",
    "introduction.create",
    "report.create",
})

# Default scopes for new installations
DEFAULT_SCOPES = [
    "registry.read",
    "profile.read",
    "task.create",
    "task.read",
    "task.inbox.read",
    "task.confirm",
]


def _hash_token(token: str) -> str:
    """SHA-256 hash of a token for safe storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _now_ts() -> float:
    return time.time()


# ── Schemas ──

class AuthorizeRequest(BaseModel):
    response_type: str = "code"
    client_id: str
    redirect_uri: str
    scope: str = Field(default="registry.read profile.read task.create task.read task.inbox.read task.confirm")
    state: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str | None = "S256"


class TokenRequest(BaseModel):
    grant_type: str  # authorization_code or refresh_token
    code: str | None = None
    redirect_uri: str | None = None
    client_id: str | None = None
    refresh_token: str | None = None
    code_verifier: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    scope: str


class IntrospectResponse(BaseModel):
    active: bool
    sub: str | None = None
    scope: str | None = None
    exp: int | None = None
    installation_id: str | None = None


# ── Endpoints ──

@router.post("/oauth/authorize")
async def authorize(req: AuthorizeRequest):
    """OAuth 2.1 Authorization endpoint.

    In production this would render a consent page. For V1.0 we issue
    the authorization code directly (assumes user has already authenticated
    via the Seabay web login flow).
    """
    if req.response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only response_type=code is supported",
        )

    # Validate requested scopes
    requested = set(req.scope.split())
    invalid = requested - VALID_SCOPES
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes: {', '.join(invalid)}",
        )

    # Generate authorization code
    code = f"seabay_ac_{secrets.token_urlsafe(32)}"
    expires_at = _now_ts() + settings.OAUTH_AUTHORIZATION_CODE_TTL

    _auth_codes[code] = {
        "subject": req.client_id,  # In production: actual user ID from session
        "scopes": list(requested),
        "redirect_uri": req.redirect_uri,
        "expires_at": expires_at,
        "code_challenge": req.code_challenge,
        "code_challenge_method": req.code_challenge_method,
    }

    logger.info("Authorization code issued for client=%s scopes=%s", req.client_id, requested)

    return {
        "code": code,
        "state": req.state,
        "redirect_uri": req.redirect_uri,
    }


@router.post("/oauth/token", response_model=TokenResponse)
async def token(req: TokenRequest):
    """OAuth 2.1 Token endpoint.

    Supports:
    - grant_type=authorization_code: exchange auth code for tokens
    - grant_type=refresh_token: refresh an expired access token
    """
    if req.grant_type == "authorization_code":
        return _exchange_code(req)
    elif req.grant_type == "refresh_token":
        return _refresh(req)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type: {req.grant_type}",
        )


@router.post("/oauth/introspect", response_model=IntrospectResponse)
async def introspect(token: str = ""):
    """Token introspection endpoint (RFC 7662).

    Returns whether a token is active and its associated metadata.
    """
    token_hash = _hash_token(token)
    token_data = _access_tokens.get(token_hash)

    if not token_data or token_data["expires_at"] < _now_ts():
        return IntrospectResponse(active=False)

    return IntrospectResponse(
        active=True,
        sub=token_data["subject"],
        scope=" ".join(token_data["scopes"]),
        exp=int(token_data["expires_at"]),
        installation_id=token_data.get("installation_id"),
    )


@router.post("/oauth/revoke")
async def revoke(token: str = ""):
    """Token revocation endpoint (RFC 7009)."""
    token_hash = _hash_token(token)
    _access_tokens.pop(token_hash, None)
    _refresh_tokens.pop(token_hash, None)
    return {"status": "revoked"}


# ── Internal Helpers ──

def _exchange_code(req: TokenRequest) -> TokenResponse:
    """Exchange authorization code for access + refresh tokens."""
    if not req.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code is required",
        )

    code_data = _auth_codes.pop(req.code, None)
    if not code_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired authorization code",
        )

    if code_data["expires_at"] < _now_ts():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code has expired",
        )

    # Verify redirect_uri matches
    if req.redirect_uri and req.redirect_uri != code_data["redirect_uri"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect_uri mismatch",
        )

    # PKCE verification (S256)
    if code_data.get("code_challenge") and req.code_verifier:
        import base64
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(req.code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        if expected != code_data["code_challenge"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PKCE code_verifier mismatch",
            )

    return _issue_tokens(code_data["subject"], code_data["scopes"])


def _refresh(req: TokenRequest) -> TokenResponse:
    """Refresh an expired access token."""
    if not req.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required",
        )

    token_hash = _hash_token(req.refresh_token)
    rt_data = _refresh_tokens.pop(token_hash, None)

    if not rt_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired refresh token",
        )

    if rt_data["expires_at"] < _now_ts():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token has expired",
        )

    return _issue_tokens(rt_data["subject"], rt_data["scopes"])


def _issue_tokens(subject: str, scopes: list[str]) -> TokenResponse:
    """Issue a new access token + refresh token pair."""
    access_token = f"seabay_at_{secrets.token_urlsafe(48)}"
    refresh_token = f"seabay_rt_{secrets.token_urlsafe(48)}"
    now = _now_ts()

    _access_tokens[_hash_token(access_token)] = {
        "subject": subject,
        "scopes": scopes,
        "installation_id": None,  # Populated after proxy agent creation
        "expires_at": now + settings.OAUTH_TOKEN_TTL,
    }

    _refresh_tokens[_hash_token(refresh_token)] = {
        "subject": subject,
        "scopes": scopes,
        "installation_id": None,
        "expires_at": now + settings.OAUTH_REFRESH_TOKEN_TTL,
    }

    logger.info("Tokens issued for subject=%s scopes=%s", subject, scopes)

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.OAUTH_TOKEN_TTL,
        refresh_token=refresh_token,
        scope=" ".join(scopes),
    )


# ── Dependency for protected routes ──

async def require_oauth(
    authorization: str = Header(None, description="Bearer access_token"),
) -> dict:
    """FastAPI dependency: validate OAuth access token.

    Returns token metadata dict: {subject, scopes, installation_id}.
    Raises 401 if token is missing, invalid, or expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth access token required. Use /oauth/authorize to obtain one.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]
    token_hash = _hash_token(token)
    token_data = _access_tokens.get(token_hash)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_data["expires_at"] < _now_ts():
        _access_tokens.pop(token_hash, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Use refresh_token to obtain a new one.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


def require_scope(required_scope: str):
    """Factory for scope-checking dependency.

    Usage:
        @router.post("/tools/create_task")
        async def create_task(auth=Depends(require_scope("task.create"))):
            ...
    """
    async def _check(auth: dict = Depends(require_oauth)) -> dict:
        if required_scope not in auth.get("scopes", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required_scope}' is required for this action",
            )
        return auth
    return _check
