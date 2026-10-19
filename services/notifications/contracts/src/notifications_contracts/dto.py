"""Data crossing the service boundary. Frozen, validated, no behaviour (rule C-2)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Channel(StrEnum):
    SMS = "sms"
    EMAIL = "email"


class DeliveryStatus(StrEnum):
    PENDING = "pending"  # recorded, provider call in flight (or the process died mid-call)
    SENT = "sent"  # a provider accepted the message
    FAILED = "failed"  # every provider in the chain refused or was unavailable


class SendRequest(BaseModel):
    """Ask Notifications to deliver one templated message.

    `recipient` is a phone in E.164 form (+14155550123) for SMS or an address for email; it is
    normalised and validated by the service. `variables` fill the template placeholders.
    """

    model_config = ConfigDict(frozen=True)

    channel: Channel
    recipient: str = Field(min_length=3, max_length=320)
    template: str = Field(min_length=1, max_length=64)
    variables: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class SendResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    delivery_id: UUID
    status: DeliveryStatus
    channel: Channel
    provider: str | None = None
    attempts: int = 0


class DeliveryInfo(BaseModel):
    """What we remember about a delivery. Never contains the message body or the full recipient."""

    model_config = ConfigDict(frozen=True)

    delivery_id: UUID
    channel: Channel
    recipient_masked: str
    template: str
    status: DeliveryStatus
    provider: str | None
    attempts: int
    error_code: str | None
    created_at: datetime
