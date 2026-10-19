"""Public contract of the notifications service. Additive changes only within a major version (rule C-10)."""

from notifications_contracts.api import NotificationsApi
from notifications_contracts.dto import (
    Channel,
    DeliveryInfo,
    DeliveryStatus,
    SendRequest,
    SendResult,
)
from notifications_contracts.errors import (
    DeliveryNotFound,
    NotificationsIdempotencyConflict,
    NotificationsInvalidRequest,
    NotificationsRateLimited,
    NotificationsUnavailable,
)
from notifications_contracts.events import DeliveryFailed
from notifications_contracts.http_client import NotificationsHttpClient

__all__ = [
    "Channel",
    "DeliveryFailed",
    "DeliveryInfo",
    "DeliveryNotFound",
    "DeliveryStatus",
    "NotificationsApi",
    "NotificationsHttpClient",
    "NotificationsIdempotencyConflict",
    "NotificationsInvalidRequest",
    "NotificationsRateLimited",
    "NotificationsUnavailable",
    "SendRequest",
    "SendResult",
]
