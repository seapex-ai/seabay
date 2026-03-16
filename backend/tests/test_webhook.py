"""Tests for webhook service — signing and delivery logic."""

from __future__ import annotations

import hashlib
import hmac

from app.services.webhook_service import RETRY_DELAYS, sign_payload


class TestWebhookSigning:
    def test_sign_payload_consistency(self):
        payload = b'{"event": "task.created", "task": {"id": "tsk_123"}}'
        secret = "test_secret"
        sig1 = sign_payload(payload, secret)
        sig2 = sign_payload(payload, secret)
        assert sig1 == sig2

    def test_sign_payload_different_secrets(self):
        payload = b'{"event": "test"}'
        sig1 = sign_payload(payload, "secret1")
        sig2 = sign_payload(payload, "secret2")
        assert sig1 != sig2

    def test_sign_payload_valid_hmac(self):
        payload = b'{"event": "test"}'
        secret = "mysecret"
        sig = sign_payload(payload, secret)
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert sig == expected


class TestRetryDelays:
    def test_retry_schedule(self):
        assert RETRY_DELAYS == [0, 1, 5, 25]

    def test_four_attempts(self):
        assert len(RETRY_DELAYS) == 4
