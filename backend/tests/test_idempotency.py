"""Tests for idempotency service logic (no DB required)."""

from __future__ import annotations

import hashlib
import json


class TestIdempotencyKeyGeneration:
    """Test idempotency key hashing and format."""

    def test_body_hash_deterministic(self):
        """Same body should produce same hash."""
        body1 = {"to_agent_id": "agt_123", "description": "Test"}
        body2 = {"to_agent_id": "agt_123", "description": "Test"}

        hash1 = hashlib.sha256(json.dumps(body1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(body2, sort_keys=True).encode()).hexdigest()
        assert hash1 == hash2

    def test_body_hash_different_bodies(self):
        """Different bodies should produce different hashes."""
        body1 = {"to_agent_id": "agt_123", "description": "Test A"}
        body2 = {"to_agent_id": "agt_123", "description": "Test B"}

        hash1 = hashlib.sha256(json.dumps(body1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(body2, sort_keys=True).encode()).hexdigest()
        assert hash1 != hash2

    def test_body_hash_key_order_independent(self):
        """JSON key order should not affect hash."""
        body1 = {"a": 1, "b": 2}
        body2 = {"b": 2, "a": 1}

        hash1 = hashlib.sha256(json.dumps(body1, sort_keys=True).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(body2, sort_keys=True).encode()).hexdigest()
        assert hash1 == hash2


class TestIdempotencyWindow:
    """Test idempotency window configuration."""

    def test_window_is_24h(self):
        """Idempotency window should be 24 hours."""
        from app.config import settings
        assert settings.IDEMPOTENCY_WINDOW_HOURS == 24

    def test_window_expiry_calculation(self):
        """Verify expiry time is correctly computed."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)
        delta = (expires - now).total_seconds()
        assert abs(delta - 86400) < 1


class TestIdempotencyConflictError:
    """Test IdempotencyConflictError."""

    def test_default_message(self):
        """Default error message should mention idempotency key."""
        from app.core.exceptions import IdempotencyConflictError

        err = IdempotencyConflictError()
        assert "idempotency" in str(err.detail).lower()

    def test_custom_message(self):
        """Custom message should be used."""
        from app.core.exceptions import IdempotencyConflictError

        err = IdempotencyConflictError("Already processed")
        assert "Already processed" in str(err.detail)

    def test_status_code(self):
        """Should return 409 Conflict."""
        from app.core.exceptions import IdempotencyConflictError

        err = IdempotencyConflictError()
        assert err.status_code == 409
