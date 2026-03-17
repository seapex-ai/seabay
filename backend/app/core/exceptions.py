"""Unified error responses per OpenAPI spec."""

from __future__ import annotations

from fastapi import HTTPException, status


class SeabayError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        super().__init__(
            status_code=status_code,
            detail={"error": {"code": code, "message": message, "details": details or {}}},
        )


class InvalidRequestError(SeabayError):
    def __init__(self, message: str = "Invalid request", details: dict | None = None):
        super().__init__(status.HTTP_400_BAD_REQUEST, "invalid_request", message, details)


class UnauthorizedError(SeabayError):
    def __init__(self, message: str = "Missing or invalid API key"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


class ForbiddenError(SeabayError):
    def __init__(self, code: str = "forbidden", message: str = "Access denied"):
        super().__init__(status.HTTP_403_FORBIDDEN, code, message)


class ContactPolicyDeniedError(ForbiddenError):
    def __init__(self):
        super().__init__("contact_policy_denied", "Target agent's contact policy does not allow this action")


class RateBudgetExceededError(ForbiddenError):
    def __init__(self):
        super().__init__("rate_budget_exceeded", "Daily rate budget exhausted for this action type")


class NotFoundError(SeabayError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(status.HTTP_404_NOT_FOUND, "not_found", f"{resource} not found")


class ConflictError(SeabayError):
    def __init__(self, code: str = "conflict", message: str = "Conflict", details: dict | None = None):
        super().__init__(status.HTTP_409_CONFLICT, code, message, details)


class InvalidStateTransitionError(ConflictError):
    def __init__(self, current: str, target: str):
        super().__init__(
            "invalid_state_transition",
            f"Cannot transition from '{current}' to '{target}'",
        )


class DLPWarningError(ConflictError):
    def __init__(self, pattern: str, override_token: str):
        super().__init__(
            "dlp_warning",
            f"Sensitive content detected: {pattern}. Include dlp_override_token to proceed.",
            {"pattern": pattern, "dlp_override_token": override_token},
        )


class DLPBlockedError(SeabayError):
    def __init__(self, pattern: str):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "dlp_blocked",
            f"Content blocked: detected {pattern}. This type of content cannot be included.",
        )


class RateLimitedError(SeabayError):
    def __init__(self):
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", "Too many requests")


class IdempotencyConflictError(ConflictError):
    def __init__(self, message: str = "Idempotency key already used with a different request body"):
        super().__init__(
            "idempotency_conflict",
            message,
        )
