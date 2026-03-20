"""Tests for exception classes — status codes, error formats."""

from __future__ import annotations

from app.core.exceptions import (
    ConflictError,
    ContactPolicyDeniedError,
    DLPBlockedError,
    DLPWarningError,
    ForbiddenError,
    IdempotencyConflictError,
    InvalidRequestError,
    InvalidStateTransitionError,
    NotFoundError,
    RateBudgetExceededError,
    RateLimitedError,
    SeabayError,
    UnauthorizedError,
)


class TestExceptionStatusCodes:
    """Test that each exception returns the correct HTTP status code."""

    def test_invalid_request_400(self):
        assert InvalidRequestError().status_code == 400

    def test_unauthorized_401(self):
        assert UnauthorizedError().status_code == 401

    def test_forbidden_403(self):
        assert ForbiddenError().status_code == 403

    def test_contact_policy_denied_403(self):
        assert ContactPolicyDeniedError().status_code == 403

    def test_rate_budget_exceeded_403(self):
        assert RateBudgetExceededError().status_code == 403

    def test_not_found_404(self):
        assert NotFoundError().status_code == 404

    def test_conflict_409(self):
        assert ConflictError().status_code == 409

    def test_dlp_warning_409(self):
        assert DLPWarningError("email", "token123").status_code == 409

    def test_dlp_blocked_400(self):
        assert DLPBlockedError("api_key").status_code == 400

    def test_rate_limited_429(self):
        assert RateLimitedError().status_code == 429

    def test_idempotency_conflict_409(self):
        assert IdempotencyConflictError().status_code == 409

    def test_invalid_state_transition_409(self):
        assert InvalidStateTransitionError("accepted", "pending_delivery").status_code == 409


class TestExceptionFormat:
    """Test that exceptions produce structured error responses."""

    def test_error_detail_structure(self):
        err = InvalidRequestError("Test error")
        detail = err.detail
        assert "error" in detail
        assert "code" in detail["error"]
        assert "message" in detail["error"]
        assert detail["error"]["code"] == "invalid_request"
        assert detail["error"]["message"] == "Test error"

    def test_not_found_includes_resource(self):
        err = NotFoundError("Agent")
        assert "Agent" in err.detail["error"]["message"]

    def test_state_transition_includes_states(self):
        err = InvalidStateTransitionError("accepted", "pending_delivery")
        msg = err.detail["error"]["message"]
        assert "accepted" in msg
        assert "pending_delivery" in msg

    def test_dlp_warning_includes_token(self):
        err = DLPWarningError("email", "tok123")
        details = err.detail["error"]["details"]
        assert details["pattern"] == "email"
        assert details["dlp_override_token"] == "tok123"

    def test_dlp_blocked_includes_pattern(self):
        err = DLPBlockedError("api_key")
        assert "api_key" in err.detail["error"]["message"]

    def test_all_errors_inherit_from_seabay_error(self):
        errors = [
            InvalidRequestError(),
            UnauthorizedError(),
            ForbiddenError(),
            NotFoundError(),
            ConflictError(),
            RateLimitedError(),
            IdempotencyConflictError(),
        ]
        for err in errors:
            assert isinstance(err, SeabayError)
