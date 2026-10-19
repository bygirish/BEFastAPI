"""The send use case end to end against a real (SQLite) database with fake providers."""

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from notifications_contracts import (
    Channel,
    DeliveryNotFound,
    DeliveryStatus,
    NotificationsApi,
    NotificationsIdempotencyConflict,
    NotificationsInvalidRequest,
    NotificationsRateLimited,
    NotificationsUnavailable,
    SendRequest,
)
from notifications_service.application.services.send_notification import (
    GetDelivery,
    SendNotification,
)
from notifications_service.infrastructure.db.models import deliveries_table, outbox_table
from notifications_service.testing import Harness, otp
from platform_core.container import Container
from platform_observability import testing as obs_testing


def api_for(harness: Harness) -> NotificationsApi:
    container = Container()
    harness.module.provide(container)
    return container.resolve(NotificationsApi)


async def rows(harness: Harness, table):  # type: ignore[no-untyped-def]
    async with harness.module.sessions() as session:
        return (await session.execute(select(table))).mappings().all()


async def test_a_message_is_rendered_sent_and_logged_without_pii(make_harness: Any) -> None:
    h: Harness = await make_harness()
    result = await api_for(h).send(otp("Asha@Example.com"))

    assert (result.status, result.provider, result.attempts) == (DeliveryStatus.SENT, "memory", 1)
    sent = h.memory.sent[0]
    assert sent.recipient == "asha@example.com"  # normalised
    assert "482913" in sent.body and sent.subject == "Your verification code"

    (row,) = await rows(h, deliveries_table)
    stored = " ".join(str(v) for v in row.values())
    assert row["recipient_masked"] == "a***@example.com"
    assert (
        "asha@example.com" not in stored and "482913" not in stored
    )  # no full address, no OTP, no body


async def test_failover_delivers_via_the_second_provider(make_harness: Any) -> None:
    h: Harness = await make_harness(email="static,memory")
    h.static.outcome = "unavailable"
    result = await api_for(h).send(otp())
    assert (result.provider, result.attempts) == ("memory", 2) and h.static.calls == 1


async def test_rejection_is_reported_logged_and_published_as_an_event(make_harness: Any) -> None:
    h: Harness = await make_harness(email="static,memory")
    h.static.outcome = "reject"
    with pytest.raises(NotificationsInvalidRequest) as info:
        await api_for(h).send(otp())
    assert info.value.code == "NOTIFICATIONS_RECIPIENT_REJECTED" and h.memory.sent == []

    (event,) = await rows(h, outbox_table)
    assert event["event_name"] == "notifications.delivery_failed.v1"
    assert "example.com" not in str(
        event["payload"]
    )  # events carry ids, never recipients (rule C-6)


async def test_total_failure_raises_unavailable_with_the_delivery_id(make_harness: Any) -> None:
    h: Harness = await make_harness(email="static")
    h.static.outcome = "unavailable"
    api = api_for(h)
    with pytest.raises(NotificationsUnavailable) as info:
        await api.send(otp())
    assert info.value.code == "NOTIFICATIONS_ALL_PROVIDERS_FAILED"
    info_after = await api.get_delivery(_uuid(info.value.details["delivery_id"]))
    assert (info_after.status, info_after.error_code) == (
        DeliveryStatus.FAILED,
        "NOTIFICATIONS_ALL_PROVIDERS_FAILED",
    )
    assert len(await rows(h, outbox_table)) == 1


async def test_an_empty_provider_chain_fails_cleanly(make_harness: Any) -> None:
    h: Harness = await make_harness(email="memory")
    h.module.settings.sms_providers.clear()
    api = api_for(h)
    with pytest.raises(NotificationsUnavailable) as info:
        await api.send(otp("+14155550123", channel=Channel.SMS))
    assert info.value.code == "NOTIFICATIONS_NO_PROVIDER_CONFIGURED"


@pytest.mark.parametrize(
    ("request_", "code"),
    [
        (otp("not-an-email"), "NOTIFICATIONS_INVALID_RECIPIENT"),
        (
            SendRequest(channel=Channel.EMAIL, recipient="a@b.co", template="nope"),
            "NOTIFICATIONS_UNKNOWN_TEMPLATE",
        ),
        (
            SendRequest(channel=Channel.EMAIL, recipient="a@b.co", template="otp", variables={}),
            "NOTIFICATIONS_TEMPLATE_VARIABLES",
        ),
    ],
)
async def test_invalid_input_is_refused_before_anything_is_stored(
    make_harness: Any, request_: SendRequest, code: str
) -> None:
    h: Harness = await make_harness()
    with pytest.raises(NotificationsInvalidRequest) as info:
        await api_for(h).send(request_)
    assert info.value.code == code
    assert await rows(h, deliveries_table) == [] and h.memory.sent == []


async def test_same_idempotency_key_sends_once_and_returns_the_first_result(
    make_harness: Any,
) -> None:
    h: Harness = await make_harness()
    api = api_for(h)
    first = await api.send(otp(idempotency_key="signup-42"))
    again = await api.send(otp(idempotency_key="signup-42"))
    assert again.delivery_id == first.delivery_id and len(h.memory.sent) == 1


async def test_reusing_a_key_for_a_different_message_is_a_conflict(make_harness: Any) -> None:
    h: Harness = await make_harness()
    api = api_for(h)
    await api.send(otp("a@example.com", idempotency_key="k"))
    with pytest.raises(NotificationsIdempotencyConflict):
        await api.send(otp("b@example.com", idempotency_key="k"))


async def test_a_failed_delivery_is_retried_on_the_same_row_with_the_same_key(
    make_harness: Any,
) -> None:
    h: Harness = await make_harness(email="static")
    h.static.outcome = "unavailable"
    api = api_for(h)
    with pytest.raises(NotificationsUnavailable) as failed:
        await api.send(otp(idempotency_key="retry-me"))
    h.static.outcome = "accept"
    ok = await api.send(otp(idempotency_key="retry-me"))
    assert str(ok.delivery_id) == failed.value.details["delivery_id"]
    assert (ok.status, ok.attempts) == (DeliveryStatus.SENT, 2)  # one failed attempt, one good one
    assert len(await rows(h, deliveries_table)) == 1


async def test_hourly_cap_per_recipient_counts_normalised_addresses(make_harness: Any) -> None:
    h: Harness = await make_harness(rate_limit_per_hour=2)
    api = api_for(h)
    await api.send(otp("asha@example.com"))
    await api.send(otp("ASHA@example.com"))  # same person, different spelling
    with pytest.raises(NotificationsRateLimited) as info:
        await api.send(otp(" Asha@Example.com "))
    assert info.value.retry_after_seconds is not None and 0 < info.value.retry_after_seconds <= 3600
    await api.send(otp("someone-else@example.com"))  # others are unaffected
    assert len(h.memory.sent) == 3


async def test_unknown_delivery_is_not_found(make_harness: Any) -> None:
    h: Harness = await make_harness()
    with pytest.raises(DeliveryNotFound):
        await api_for(h).get_delivery(uuid4())


async def test_in_process_calls_are_attributed_to_the_notifications_service(
    make_harness: Any, telemetry: obs_testing.Telemetry
) -> None:
    """The contract call runs inside the CALLER's request context; contracts_impl re-scopes it to this service,
    otherwise the span would be named after the caller (`app.SendNotification`) and dashboards would mis-attribute it."""
    h: Harness = await make_harness(email="static,memory")
    h.static.outcome = "unavailable"
    telemetry.clear()
    await api_for(h).send(otp())
    assert "notifications.SendNotification" in telemetry.span_names()
    assert "app.SendNotification" not in telemetry.span_names()
    attempts = telemetry.data_points("notifications.provider.attempt")
    assert {
        "channel": "email",
        "provider": "static",
        "outcome": "unavailable",
        "app.service": "notifications",
    } in attempts
    assert any(p.get("outcome") == "sent" for p in telemetry.data_points("notifications.delivery"))


def _uuid(value: str):  # type: ignore[no-untyped-def]
    from uuid import UUID

    return UUID(value)


_ = (SendNotification, GetDelivery)


async def test_every_series_exists_at_zero_from_startup(
    make_harness: Any, telemetry: obs_testing.Telemetry
) -> None:
    """Regression (found in the live run): a counter born at 3 has no rate(), so early failures were invisible to the SLO."""
    h: Harness = await make_harness(email="static,memory")
    api_for(h)  # providing the module primes the metrics
    deliveries = telemetry.data_points("notifications.delivery")
    for channel in ("sms", "email"):
        for outcome in ("sent", "rejected", "failed"):
            assert {
                "channel": channel,
                "outcome": outcome,
                "app.service": "notifications",
            } in deliveries
    attempts = telemetry.data_points("notifications.provider.attempt")
    assert {
        "channel": "email",
        "provider": "static",
        "outcome": "unavailable",
        "app.service": "notifications",
    } in attempts


def test_priming_creates_a_series_nothing_else_has_touched(
    telemetry: obs_testing.Telemetry,
) -> None:
    from notifications_service.application.telemetry import prime_metrics

    wanted = {
        "channel": "sms",
        "provider": "smtp",
        "outcome": "timeout",
        "app.service": "notifications",
    }
    assert wanted not in telemetry.data_points(
        "notifications.provider.attempt"
    )  # no test ever produces this
    prime_metrics({"sms": ["smtp"]})
    assert wanted in telemetry.data_points("notifications.provider.attempt")
