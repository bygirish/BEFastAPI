"""Versioned integration events: past-tense facts, IDs + minimal fields (rules C-6, C-8). No PII."""

from typing import ClassVar
from uuid import UUID

from notifications_contracts.dto import Channel
from platform_events import IntegrationEvent


class DeliveryFailed(IntegrationEvent):
    """Every provider in the chain failed (or the recipient was rejected). Subscribers may alert or fall back."""

    EVENT_NAME: ClassVar[str] = "notifications.delivery_failed.v1"

    delivery_id: UUID
    channel: Channel
    template: str
    error_code: str
