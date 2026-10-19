"""The vendor-neutral gateway: one place that knows how to walk a provider chain.

Callers (and the use case) see `deliver(message)`; whether that is Twilio, an SMTP relay or a console printer
is a configuration choice. Policy, in one paragraph:

* try providers in order; each call is bounded by a per-attempt timeout;
* a *rejection* (permanent refusal) stops the walk — another vendor won't fix a bad number;
* *unavailable* / *timeout* / any unexpected adapter exception fails over to the next provider;
* the result lists every attempt, so the caller can persist and observe them.
"""

import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from notifications_contracts import Channel
from notifications_service.application.ports import (
    OutboundMessage,
    Sender,
    SenderRejected,
    SenderUnavailable,
)
from notifications_service.application.telemetry import PROVIDER_ATTEMPTS, PROVIDER_DURATION
from platform_observability import get_logger


class AttemptOutcome(StrEnum):
    SENT = "sent"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class Attempt:
    provider: str
    outcome: AttemptOutcome
    seconds: float


@dataclass(frozen=True)
class GatewayResult:
    attempts: tuple[Attempt, ...]

    @property
    def last(self) -> Attempt | None:
        return self.attempts[-1] if self.attempts else None

    @property
    def sent(self) -> bool:
        return self.last is not None and self.last.outcome is AttemptOutcome.SENT

    @property
    def rejected(self) -> bool:
        return self.last is not None and self.last.outcome is AttemptOutcome.REJECTED

    @property
    def provider(self) -> str | None:
        return self.last.provider if self.sent and self.last else None


class NotificationGateway:
    def __init__(
        self, chains: Mapping[Channel, Sequence[Sender]], *, attempt_timeout_seconds: float
    ) -> None:
        self._chains = {channel: tuple(senders) for channel, senders in chains.items()}
        self._timeout = attempt_timeout_seconds
        self._log = get_logger("notifications.gateway")

    def providers_for(self, channel: Channel) -> tuple[str, ...]:
        return tuple(s.name for s in self._chains.get(channel, ()))

    async def deliver(self, message: OutboundMessage) -> GatewayResult:
        attempts: list[Attempt] = []
        for sender in self._chains.get(message.channel, ()):
            attempt = await self._try(sender, message)
            attempts.append(attempt)
            PROVIDER_ATTEMPTS.add(
                channel=message.channel.value, provider=sender.name, outcome=attempt.outcome.value
            )
            PROVIDER_DURATION.record(
                attempt.seconds, channel=message.channel.value, provider=sender.name
            )
            if attempt.outcome in (AttemptOutcome.SENT, AttemptOutcome.REJECTED):
                break
            self._log.warning(
                "provider_failover",
                channel=message.channel.value,
                provider=sender.name,
                outcome=attempt.outcome.value,
            )
        return GatewayResult(tuple(attempts))

    async def _try(self, sender: Sender, message: OutboundMessage) -> Attempt:
        started = time.perf_counter()
        outcome = AttemptOutcome.SENT
        try:
            async with asyncio.timeout(self._timeout):
                await sender.send(message)
        except SenderRejected:
            outcome = AttemptOutcome.REJECTED
        except SenderUnavailable:
            outcome = AttemptOutcome.UNAVAILABLE
        except TimeoutError:
            outcome = AttemptOutcome.TIMEOUT
        except Exception as exc:  # noqa: BLE001 - a buggy third-party adapter must not take the gateway down
            self._log.error("provider_crashed", provider=sender.name, error_type=type(exc).__name__)
            outcome = AttemptOutcome.UNAVAILABLE
        return Attempt(sender.name, outcome, time.perf_counter() - started)
