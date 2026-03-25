"""MCP Edge configuration.

Environment-based settings for the MCP Edge server.
All settings use the MCPEDGE_ prefix.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class EdgeSettings(BaseSettings):
    # Application
    APP_NAME: str = "Seabay MCP Edge"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8100

    # Core API connection
    SEABAY_CORE_URL: str = "http://localhost:8000/v1"
    CORE_REQUEST_TIMEOUT: float = 30.0

    # Redis for token storage
    REDIS_URL: str = "redis://localhost:6379/1"

    # OAuth 2.1 settings
    OAUTH_ISSUER: str = "https://mcp.seabay.ai"
    OAUTH_TOKEN_TTL: int = 3600  # 1 hour
    OAUTH_REFRESH_TOKEN_TTL: int = 86400 * 30  # 30 days
    OAUTH_AUTHORIZATION_CODE_TTL: int = 600  # 10 minutes

    # Internal JWT signing (Edge -> Core)
    JWT_SECRET_KEY: str = "DO-NOT-USE-IN-PRODUCTION-edge-dev-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_TTL: int = 300  # 5 minutes for internal calls

    # Rate limits
    RATE_LIMIT_AUTHLESS: int = 60  # per minute per IP
    RATE_LIMIT_AUTHENTICATED: int = 120  # per minute per token

    # Risk gate
    RISK_REQUIRE_CONFIRM: list[str] = ["R2", "R3"]

    # Audit
    AUDIT_LOG_ENABLED: bool = True

    # Transport
    SSE_KEEPALIVE_INTERVAL: int = 15  # seconds

    # Fallback
    FALLBACK_BASE_URL: str = "https://app.seabay.ai"

    model_config = {"env_prefix": "MCPEDGE_", "env_file": ".env"}


settings = EdgeSettings()
