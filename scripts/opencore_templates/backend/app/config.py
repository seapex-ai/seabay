from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Seabay"
    APP_VERSION: str = "0.1.1"
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

    # Public open-core defaults intentionally disable operational enforcement.
    # Self-hosted operators should set their own policies via environment.
    RATE_LIMIT_REGISTER: int = 0
    RATE_LIMIT_SEARCH: int = 0
    RATE_LIMIT_POST: int = 0
    RATE_LIMIT_READ: int = 0
    RATE_LIMIT_PUBLIC: int = 0

    # Task Defaults
    TASK_DEFAULT_TTL_PERSONAL: int = 259200
    TASK_DEFAULT_TTL_SERVICE: int = 86400
    TASK_DELIVERY_MAX_ATTEMPTS: int = 4
    TASK_HUMAN_CONFIRM_TIMEOUT_R2: int = 14400
    TASK_HUMAN_CONFIRM_TIMEOUT_R3: int = 43200

    # Anti-Spam Budgets (personal agents)
    BUDGET_NEW_DIRECT_TASK_DAILY: int = 5
    BUDGET_INTRODUCTION_DAILY: int = 3
    BUDGET_CIRCLE_REQUEST_DAILY: int = 5

    # Report Thresholds
    REPORT_SOFT_FREEZE_THRESHOLD: int = 3
    REPORT_SUSPEND_THRESHOLD: int = 5

    # Online Status
    ONLINE_AWAY_THRESHOLD: int = 300
    ONLINE_OFFLINE_THRESHOLD: int = 1800

    # Idempotency
    IDEMPOTENCY_WINDOW_HOURS: int = 24

    # Circle
    CIRCLE_MAX_MEMBERS: int = 30

    # Introduction TTL
    INTRODUCTION_TTL_HOURS: int = 72

    model_config = {"env_prefix": "SEABAY_", "env_file": ".env"}


settings = Settings()
