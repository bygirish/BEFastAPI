"""Contract-level errors. The in-process implementation raises the same ones as the HTTP client (rule C-4)."""

from platform_core.errors import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    RateLimitedError,
    UnavailableError,
)


class NotificationsInvalidRequest(InvalidInputError):
    """Bad recipient/template/variables, or the provider rejected the recipient (the code says which)."""

    default_code = "NOTIFICATIONS_INVALID_REQUEST"
    default_message = "The notification request is invalid."


class NotificationsRateLimited(RateLimitedError):
    default_code = "NOTIFICATIONS_RATE_LIMITED"
    default_message = "Too many messages were sent to this recipient recently."


class NotificationsIdempotencyConflict(ConflictError):
    default_code = "NOTIFICATIONS_IDEMPOTENCY_CONFLICT"
    default_message = (
        "This idempotency key was already used for a different message, or is still in flight."
    )


class DeliveryNotFound(NotFoundError):
    default_code = "NOTIFICATIONS_DELIVERY_NOT_FOUND"
    default_message = "No such delivery."


class NotificationsUnavailable(UnavailableError):
    """No provider could deliver the message (details carry the delivery id), or the service itself is down."""

    default_code = "NOTIFICATIONS_UNAVAILABLE"
    default_message = "The notifications service is unavailable."
