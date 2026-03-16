"""Tests for application configuration (settings defaults)."""

from __future__ import annotations

from app.config import Settings


class TestConfigDefaults:
    """Verify all config defaults match spec."""

    def test_app_name(self):
        s = Settings()
        assert s.APP_NAME == "Seabay"

    def test_region_default(self):
        s = Settings()
        assert s.REGION == "intl"

    def test_api_prefix(self):
        s = Settings()
        assert s.API_V1_PREFIX == "/v1"

    def test_api_key_prefix(self):
        s = Settings()
        assert s.API_KEY_PREFIX == "sk_live_"

    def test_bcrypt_rounds(self):
        s = Settings()
        assert s.BCRYPT_ROUNDS == 12

    def test_task_ttl_personal(self):
        s = Settings()
        assert s.TASK_DEFAULT_TTL_PERSONAL == 259200  # 72h

    def test_task_ttl_service(self):
        s = Settings()
        assert s.TASK_DEFAULT_TTL_SERVICE == 86400  # 24h

    def test_delivery_max_attempts(self):
        s = Settings()
        assert s.TASK_DELIVERY_MAX_ATTEMPTS == 4  # spec: 1 initial + 3 retries = 4 total

    def test_human_confirm_r2_timeout(self):
        s = Settings()
        assert s.TASK_HUMAN_CONFIRM_TIMEOUT_R2 == 14400  # 4h

    def test_human_confirm_r3_timeout(self):
        s = Settings()
        assert s.TASK_HUMAN_CONFIRM_TIMEOUT_R3 == 43200  # 12h

    def test_budget_new_direct_task(self):
        s = Settings()
        assert s.BUDGET_NEW_DIRECT_TASK_DAILY == 5

    def test_budget_introduction(self):
        s = Settings()
        assert s.BUDGET_INTRODUCTION_DAILY == 3

    def test_budget_circle_request(self):
        s = Settings()
        assert s.BUDGET_CIRCLE_REQUEST_DAILY == 5

    def test_report_thresholds(self):
        s = Settings()
        assert s.REPORT_SOFT_FREEZE_THRESHOLD == 3
        assert s.REPORT_SUSPEND_THRESHOLD == 5

    def test_online_thresholds(self):
        s = Settings()
        assert s.ONLINE_AWAY_THRESHOLD == 300       # 5 min
        assert s.ONLINE_OFFLINE_THRESHOLD == 1800   # 30 min

    def test_idempotency_window(self):
        s = Settings()
        assert s.IDEMPOTENCY_WINDOW_HOURS == 24

    def test_circle_max_members(self):
        s = Settings()
        assert s.CIRCLE_MAX_MEMBERS == 30

    def test_introduction_ttl(self):
        s = Settings()
        assert s.INTRODUCTION_TTL_HOURS == 72  # spec: 72h (SQL schema 259200s)

    def test_rate_limits(self):
        s = Settings()
        assert s.RATE_LIMIT_REGISTER == 10
        assert s.RATE_LIMIT_SEARCH == 100
        assert s.RATE_LIMIT_POST == 60
        assert s.RATE_LIMIT_READ == 120
        assert s.RATE_LIMIT_PUBLIC == 60


class TestConfigEnvPrefix:
    """Test that config uses correct env prefix."""

    def test_env_prefix_is_seabay(self):
        assert Settings.model_config.get("env_prefix") == "SEABAY_"
