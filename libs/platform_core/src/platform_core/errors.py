"""Error taxonomy shared by all services (rule X-3).

Domain/application code raises these (or service subclasses carrying a service-prefixed
`code`, e.g. ``AUTH_ACCOUNT_LOCKED``). The HTTP edge (platform_http) maps *categories*
to status codes; nothing here knows about HTTP.
"""

from typing import Any


class AppError(Exception):
    default_code = "APP_ERROR"
    default_message = "An error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details: dict[str, Any] = details or {}
        super().__init__(self.message)


class InvalidInputError(AppError):
    default_code = "INVALID_INPUT"
    default_message = "The request is invalid."


class UnauthenticatedError(AppError):
    default_code = "UNAUTHENTICATED"
    default_message = "Authentication is required."


class ForbiddenError(AppError):
    default_code = "FORBIDDEN"
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    default_code = "NOT_FOUND"
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    default_code = "CONFLICT"
    default_message = "The request conflicts with the current state."


class RateLimitedError(AppError):
    default_code = "RATE_LIMITED"
    default_message = "Too many requests."

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after_seconds: int | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
        self.retry_after_seconds = retry_after_seconds


class UnavailableError(AppError):
    """A dependency (another service, vendor, DB) is unavailable. Callers may retry."""

    default_code = "UNAVAILABLE"
    default_message = "A required dependency is temporarily unavailable."


class DependencyTimeoutError(UnavailableError):
    default_code = "DEPENDENCY_TIMEOUT"
    default_message = "A required dependency did not respond in time."


# Errors caused by the caller: telemetry must not mark spans as failed for these (O-6).
CLIENT_ERROR_TYPES: tuple[type[AppError], ...] = (
    InvalidInputError,
    UnauthenticatedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    RateLimitedError,
)
