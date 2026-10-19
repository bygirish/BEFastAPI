"""What other services may ask of notifications. Coarse-grained, batchable, DTOs only (rules C-2, C-3)."""

from typing import Protocol
from uuid import UUID

from notifications_contracts.dto import DeliveryInfo, SendRequest, SendResult


class NotificationsApi(Protocol):
    async def send(self, request: SendRequest) -> SendResult:
        """Deliver one templated message, failing over between providers.

        Raises NotificationsInvalidRequest (bad input or recipient rejected), NotificationsRateLimited,
        NotificationsIdempotencyConflict, or NotificationsUnavailable (no provider could deliver).
        Re-sending with the same `idempotency_key` after a success returns the first result.
        """
        ...

    async def get_delivery(self, delivery_id: UUID) -> DeliveryInfo:
        """Raises DeliveryNotFound."""
        ...
