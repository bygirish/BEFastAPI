"""DEV/TEST ONLY: a provider with a fixed, configurable answer — to rehearse failover and rejection deterministically."""

from typing import Literal

from notifications_contracts import Channel
from notifications_service.application.ports import (
    OutboundMessage,
    SenderRejected,
    SenderUnavailable,
)

StaticOutcome = Literal["accept", "reject", "unavailable"]


class StaticSender:
    name = "static"
    channels = frozenset(Channel)

    def __init__(self, outcome: StaticOutcome = "accept") -> None:
        self.outcome = outcome
        self.calls = 0

    async def send(self, message: OutboundMessage) -> None:
        self.calls += 1
        if self.outcome == "reject":
            raise SenderRejected("static provider is configured to reject")
        if self.outcome == "unavailable":
            raise SenderUnavailable("static provider is configured to be down")
