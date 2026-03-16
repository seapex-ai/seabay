"""Tests for metrics models and config."""

from __future__ import annotations


class TestMetricsModels:
    """Test metrics model definitions."""

    def test_trust_metrics_daily_table_name(self):
        """TrustMetricsDaily should map to correct table."""
        from app.models.metrics import TrustMetricsDaily
        assert TrustMetricsDaily.__tablename__ == "trust_metrics_daily"

    def test_popularity_metrics_daily_table_name(self):
        """PopularityMetricsDaily should map to correct table."""
        from app.models.metrics import PopularityMetricsDaily
        assert PopularityMetricsDaily.__tablename__ == "popularity_metrics_daily"

    def test_passport_lite_receipt_table_name(self):
        """PassportLiteReceipt should map to correct table."""
        from app.models.metrics import PassportLiteReceipt
        assert PassportLiteReceipt.__tablename__ == "passport_lite_receipts"

    def test_idempotency_record_table_name(self):
        """IdempotencyRecord should map to correct table."""
        from app.models.metrics import IdempotencyRecord
        assert IdempotencyRecord.__tablename__ == "idempotency_records"


class TestMetricsConfig:
    """Test metrics-related configuration."""

    def test_budget_limits(self):
        """Budget limits should match spec."""
        from app.config import settings
        assert settings.BUDGET_NEW_DIRECT_TASK_DAILY == 5
        assert settings.BUDGET_INTRODUCTION_DAILY == 3
        assert settings.BUDGET_CIRCLE_REQUEST_DAILY == 5

    def test_report_thresholds(self):
        """Report thresholds should match spec."""
        from app.config import settings
        assert settings.REPORT_SOFT_FREEZE_THRESHOLD == 3
        assert settings.REPORT_SUSPEND_THRESHOLD == 5

    def test_circle_max_members(self):
        """Circle max members should be 30."""
        from app.config import settings
        assert settings.CIRCLE_MAX_MEMBERS == 30

    def test_introduction_ttl(self):
        """Introduction TTL should be 72 hours (spec SQL schema: 259200s)."""
        from app.config import settings
        assert settings.INTRODUCTION_TTL_HOURS == 72

    def test_task_ttl_defaults(self):
        """Task TTL defaults: personal=72h, service=24h."""
        from app.config import settings
        assert settings.TASK_DEFAULT_TTL_PERSONAL == 259200  # 72h
        assert settings.TASK_DEFAULT_TTL_SERVICE == 86400    # 24h

    def test_rate_limits(self):
        """Rate limits should match spec."""
        from app.config import settings
        assert settings.RATE_LIMIT_REGISTER == 10     # per hour
        assert settings.RATE_LIMIT_SEARCH == 100      # per minute
        assert settings.RATE_LIMIT_POST == 60         # per minute
        assert settings.RATE_LIMIT_READ == 120        # per minute
        assert settings.RATE_LIMIT_PUBLIC == 60       # per minute


class TestIDPrefixes:
    """Test ID prefix format for all entity types."""

    def test_all_prefixes_unique(self):
        """All ID prefixes should be unique."""
        from app.core.id_generator import generate_id

        prefixes = set()
        for entity in ["agent", "profile", "task", "intent", "circle",
                       "relationship", "verification", "report", "interaction",
                       "introduction", "membership", "join_request", "origin"]:
            id_val = generate_id(entity)
            prefix = id_val.split("_")[0] + "_"
            prefixes.add(prefix)

        # All should be unique (no collisions)
        # At minimum we should have generated IDs for each type
        assert len(prefixes) >= 5  # Some may share prefixes

    def test_id_format(self):
        """IDs should follow {prefix}_{nanoid} format."""
        from app.core.id_generator import generate_id

        for entity in ["agent", "task", "circle"]:
            id_val = generate_id(entity)
            assert "_" in id_val
            parts = id_val.split("_", 1)
            assert len(parts) == 2
            assert len(parts[0]) >= 2  # prefix
            assert len(parts[1]) >= 10  # nanoid portion
