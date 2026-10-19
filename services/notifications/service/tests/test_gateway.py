"""The gateway's failover policy, with scripted fake providers."""

import asyncio

import pytest

from notifications_contracts import Channel
from notifications_service.application.gateway import AttemptOutcome, NotificationGateway
from notifications_service.application.ports import (
    OutboundMessage,
    SenderRejected,
    SenderUnavailable,
)

MESSAGE = OutboundMessage(Channel.SMS, "+14155550123", None, "hi")


class Scripted:
    channels = frozenset(Channel)

    def __init__(self, name: str, behaviour: str = "ok") -> None:
        self.name, self.behaviour, self.calls = name, behaviour, 0

    async def send(self, message: OutboundMessage) -> None:
        self.calls += 1
        match self.behaviour:
            case "reject":
                raise SenderRejected("no")
            case "down":
                raise SenderUnavailable("down")
            case "hang":
                await asyncio.sleep(10)
            case "bug":
                raise KeyError("adapter bug")


def gateway(*senders: Scripted, timeout: float = 0.05) -> NotificationGateway:
    return NotificationGateway({Channel.SMS: list(senders)}, attempt_timeout_seconds=timeout)


async def test_first_healthy_provider_wins_and_later_ones_are_untouched() -> None:
    a, b = Scripted("console"), Scripted("static")
    result = await gateway(a, b).deliver(MESSAGE)
    assert result.sent and result.provider == "console" and (a.calls, b.calls) == (1, 0)


async def test_unavailable_provider_fails_over_to_the_next() -> None:
    a, b = Scripted("console", "down"), Scripted("static")
    result = await gateway(a, b).deliver(MESSAGE)
    assert result.sent and result.provider == "static"
    assert [x.outcome for x in result.attempts] == [AttemptOutcome.UNAVAILABLE, AttemptOutcome.SENT]


async def test_rejection_stops_the_chain() -> None:
    a, b = Scripted("console", "reject"), Scripted("static")
    result = await gateway(a, b).deliver(MESSAGE)
    assert (
        result.rejected and not result.sent and b.calls == 0
    )  # another vendor won't fix a bad number


async def test_a_hanging_provider_times_out_and_fails_over() -> None:
    result = await gateway(Scripted("console", "hang"), Scripted("static")).deliver(MESSAGE)
    assert [x.outcome for x in result.attempts] == [AttemptOutcome.TIMEOUT, AttemptOutcome.SENT]


async def test_a_crashing_adapter_is_treated_as_unavailable() -> None:
    result = await gateway(Scripted("console", "bug"), Scripted("static")).deliver(MESSAGE)
    assert result.sent and result.attempts[0].outcome is AttemptOutcome.UNAVAILABLE


async def test_everything_down_reports_every_attempt() -> None:
    result = await gateway(Scripted("console", "down"), Scripted("static", "down")).deliver(MESSAGE)
    assert (
        not result.sent
        and not result.rejected
        and len(result.attempts) == 2
        and result.provider is None
    )


async def test_an_empty_chain_is_a_failure_not_a_crash() -> None:
    result = await NotificationGateway({}, attempt_timeout_seconds=1).deliver(MESSAGE)
    assert not result.sent and result.attempts == ()


@pytest.mark.parametrize("channel", list(Channel))
def test_gateway_reports_its_chain_per_channel(channel: Channel) -> None:
    gw = NotificationGateway(
        {channel: [Scripted("console"), Scripted("static")]}, attempt_timeout_seconds=1
    )
    assert gw.providers_for(channel) == ("console", "static")
