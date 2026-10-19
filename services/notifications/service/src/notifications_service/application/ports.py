"""Interfaces this service needs from the outside (repositories, UoW, providers…). Rule L-3."""

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from notifications_contracts import Channel
from notifications_service.domain.delivery import Delivery
from platform_events import OutboxWriter


@dataclass(frozen=True)
class OutboundMessage:
    channel: Channel
    recipient: str
    subject: str | None
    body: str


class SenderRejected(Exception):
    """The provider understood the request and refused it permanently (bad number, blocked address).

    Trying another provider would not help and might annoy the recipient, so the gateway stops here.
    """


class SenderUnavailable(Exception):
    """The provider could not be reached or had a transient problem. The gateway fails over."""


class Sender(Protocol):
    """One provider adapter (a Twilio-ish SMS vendor, an SMTP relay, …). The only vendor-specific code."""

    name: str
    channels: frozenset[Channel]

    async def send(self, message: OutboundMessage) -> None:
        """Return normally when the provider ACCEPTED the message. Raise SenderRejected/SenderUnavailable otherwise."""
        ...


class SentMessageLog(Protocol):
    """Lets the dev-only endpoint show what the in-memory sender captured."""

    def messages(self) -> list[OutboundMessage]: ...


class DuplicateKey(Exception):
    """Another delivery already holds this idempotency key (lost a race)."""


class DeliveryRepository(Protocol):
    async def add(self, delivery: Delivery) -> None: ...

    async def update(self, delivery: Delivery) -> None: ...

    async def get(self, delivery_id: UUID) -> Delivery | None: ...

    async def find_by_key(self, key: str) -> Delivery | None: ...

    async def created_since(self, digest: str, since: datetime) -> list[datetime]:
        """Creation times (oldest first) of this recipient's deliveries since `since`."""
        ...


class UnitOfWork(Protocol):
    @property
    def outbox(self) -> OutboxWriter: ...

    @property
    def deliveries(self) -> DeliveryRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
