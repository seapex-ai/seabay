"""Tests for passport service — signing and verification logic."""

from __future__ import annotations

import hashlib
import hmac
import json

from app.services.passport_service import SIGNING_KEY, _sign_payload


class TestPassportSigning:
    """Test passport receipt signing."""

    def test_sign_payload_deterministic(self):
        """Same payload should produce same signature."""
        payload = {
            "agent_id": "agt_123",
            "display_name": "Test Agent",
            "trust_score": 65.0,
        }
        sig1 = _sign_payload(payload)
        sig2 = _sign_payload(payload)
        assert sig1 == sig2

    def test_sign_payload_different_data(self):
        """Different payloads should produce different signatures."""
        payload1 = {"agent_id": "agt_123", "trust_score": 65.0}
        payload2 = {"agent_id": "agt_456", "trust_score": 65.0}
        assert _sign_payload(payload1) != _sign_payload(payload2)

    def test_sign_payload_uses_hmac_sha256(self):
        """Signature should be valid HMAC-SHA256."""
        payload = {"agent_id": "agt_123", "trust_score": 50.0}
        signature = _sign_payload(payload)

        # Verify manually
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        expected = hmac.new(
            SIGNING_KEY.encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert signature == expected

    def test_sign_payload_hex_format(self):
        """Signature should be hex string."""
        payload = {"test": "data"}
        signature = _sign_payload(payload)
        assert len(signature) == 64  # SHA256 hex digest is 64 chars
        assert all(c in "0123456789abcdef" for c in signature)

    def test_sign_payload_key_order_independent(self):
        """JSON sort_keys ensures key order doesn't matter."""
        payload1 = {"a": 1, "b": 2, "c": 3}
        payload2 = {"c": 3, "a": 1, "b": 2}
        assert _sign_payload(payload1) == _sign_payload(payload2)


class TestPassportConfig:
    """Test passport configuration."""

    def test_receipt_validity_default(self):
        """Default receipt validity should be 90 days."""
        from app.services.passport_service import RECEIPT_VALIDITY_DAYS
        assert RECEIPT_VALIDITY_DAYS == 90

    def test_signing_key_not_empty(self):
        """Signing key should not be empty."""
        assert len(SIGNING_KEY) > 0
