"""The Delivery entity: our record of one attempt to reach one recipient (never the message body)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from notifications_contracts import Channel, DeliveryStatus


@dataclass
class Delivery:
    id: UUID
    channel: Channel
    recipient_masked: str
    recipient_digest: str
    template: str
    created_at: datetime
    updated_at: datetime
    status: DeliveryStatus = DeliveryStatus.PENDING
    provider: str | None = None
    attempts: int = 0
    error_code: str | None = None
    idempotency_key: str | None = None

    def mark_sent(self, *, provider: str, attempts: int, now: datetime) -> None:
        self.status = DeliveryStatus.SENT
        self.provider = provider
        self.attempts += attempts
        self.error_code = None
        self.updated_at = now

    def mark_failed(self, *, error_code: str, attempts: int, now: datetime) -> None:
        self.status = DeliveryStatus.FAILED
        self.attempts += attempts
        self.error_code = error_code
        self.updated_at = now

    def reopen(self, now: datetime) -> None:
        """A failed delivery retried under the same idempotency key gets another go on the same row."""
        self.status = DeliveryStatus.PENDING
        self.updated_at = now
