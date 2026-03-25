from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Seabay"
    APP_VERSION: str = "0.1.3"
    DEBUG: bool = False
    REGION: str = "intl"
    API_V1_PREFIX: str = "/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://seabay:seabay@localhost:5432/seabay"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    API_KEY_PREFIX: str = "sk_live_"
    BCRYPT_ROUNDS: int = 12
    CORS_ORIGINS: str = "*"
    PASSPORT_SIGNING_KEY: str = "DO-NOT-USE-IN-PRODUCTION-dev-only"

    # Rate Limits
    RATE_LIMIT_REGISTER: int = 10          # per hour per IP
    RATE_LIMIT_SEARCH: int = 100           # per minute per key
    RATE_LIMIT_POST: int = 60              # per minute per key
    RATE_LIMIT_READ: int = 120             # per minute per key
    RATE_LIMIT_PUBLIC: int = 60            # per minute per IP

    # Task Defaults
    TASK_DEFAULT_TTL_PERSONAL: int = 259200   # 72h in seconds
    TASK_DEFAULT_TTL_SERVICE: int = 86400     # 24h in seconds
    TASK_DELIVERY_MAX_ATTEMPTS: int = 4
    TASK_HUMAN_CONFIRM_TIMEOUT_R2: int = 14400   # 4h in seconds
    TASK_HUMAN_CONFIRM_TIMEOUT_R3: int = 43200   # 12h in seconds

    # Anti-Spam Budgets (personal agents)
    BUDGET_NEW_DIRECT_TASK_DAILY: int = 5
    BUDGET_INTRODUCTION_DAILY: int = 3
    BUDGET_CIRCLE_REQUEST_DAILY: int = 5

    # Report Thresholds
    REPORT_SOFT_FREEZE_THRESHOLD: int = 3
    REPORT_SUSPEND_THRESHOLD: int = 5

    # Online Status
    ONLINE_AWAY_THRESHOLD: int = 300       # 5 min
    ONLINE_OFFLINE_THRESHOLD: int = 1800   # 30 min

    # Idempotency
    IDEMPOTENCY_WINDOW_HOURS: int = 24

    # Circle
    CIRCLE_MAX_MEMBERS: int = 30

    # Introduction TTL
    INTRODUCTION_TTL_HOURS: int = 72

    # Domain Verification
    # True = auto-verify in dev (skip DNS lookup); False = require actual DNS TXT lookup
    DOMAIN_VERIFICATION_AUTO: bool = True

    model_config = {"env_prefix": "SEABAY_", "env_file": ".env"}


settings = Settings()
