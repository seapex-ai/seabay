"""Tests for verification_service — code generation, expiry, level computation."""

from __future__ import annotations

from app.services import verification_service


class TestVerificationHelpers:
    """Test verification helper functions (no DB required)."""

    def test_check_pending_raises_on_verified(self):
        """_check_pending should raise if not pending."""
        from unittest.mock import MagicMock

        from app.core.exceptions import InvalidRequestError

        v = MagicMock()
        v.status = "verified"
        try:
            verification_service._check_pending(v)
            assert False, "Should have raised"
        except InvalidRequestError as e:
            assert "verified" in str(e.detail)

    def test_check_pending_passes_on_pending(self):
        """_check_pending should not raise if pending."""
        from unittest.mock import MagicMock

        v = MagicMock()
        v.status = "pending"
        verification_service._check_pending(v)  # no exception

    def test_check_code_expiry_raises_on_expired(self):
        """_check_code_expiry should raise if code expired."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock

        from app.core.exceptions import InvalidRequestError

        v = MagicMock()
        v.code_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        try:
            verification_service._check_code_expiry(v)
            assert False, "Should have raised"
        except InvalidRequestError:
            assert v.status == "expired"

    def test_check_code_expiry_passes_on_valid(self):
        """_check_code_expiry should not raise if code not expired."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock

        v = MagicMock()
        v.code_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        verification_service._check_code_expiry(v)  # no exception

    def test_check_code_expiry_none_is_ok(self):
        """_check_code_expiry should not raise if no expiry set."""
        from unittest.mock import MagicMock

        v = MagicMock()
        v.code_expires_at = None
        verification_service._check_code_expiry(v)  # no exception


class TestVerificationWeights:
    """Test verification level weight computation logic."""

    def test_verification_weight_order(self):
        """Verification weights should follow none < email < github/domain < workspace < manual_review."""
        from app.models.enums import VERIFICATION_WEIGHTS, VerificationLevel

        assert VERIFICATION_WEIGHTS[VerificationLevel.NONE] == 0
        assert VERIFICATION_WEIGHTS[VerificationLevel.EMAIL] == 1
        assert VERIFICATION_WEIGHTS[VerificationLevel.GITHUB] == 2
        assert VERIFICATION_WEIGHTS[VerificationLevel.DOMAIN] == 2
        assert VERIFICATION_WEIGHTS[VerificationLevel.WORKSPACE] == 3
        assert VERIFICATION_WEIGHTS[VerificationLevel.MANUAL_REVIEW] == 4

    def test_github_and_domain_same_weight(self):
        """GitHub and domain should have the same weight."""
        from app.models.enums import VERIFICATION_WEIGHTS, VerificationLevel

        assert VERIFICATION_WEIGHTS[VerificationLevel.GITHUB] == VERIFICATION_WEIGHTS[VerificationLevel.DOMAIN]
