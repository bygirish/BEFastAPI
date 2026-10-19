"""Contract tests (rule T-3): the SAME assertions run against the in-process implementation and the
HTTP client talking to the real /internal routes. This is what makes extraction a wiring change."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport

from notifications_contracts import (
    Channel,
    DeliveryNotFound,
    DeliveryStatus,
    NotificationsApi,
    NotificationsHttpClient,
    NotificationsIdempotencyConflict,
    NotificationsInvalidRequest,
    NotificationsRateLimited,
    NotificationsUnavailable,
)
from notifications_service.testing import Harness, otp
from platform_http import ServiceHttpClient, create_application
from platform_security.testing import TestAuth


@pytest.fixture(params=["in_process", "http"])
async def setup(
    request: pytest.FixtureRequest, make_harness: Any, auth: TestAuth
) -> AsyncIterator[tuple[NotificationsApi, Harness]]:
    h: Harness = await make_harness(email="static,memory", rate_limit_per_hour=3)
    app = create_application(
        title="t",
        service_name="notifications-tests",
        modules=[h.module],
        telemetry=False,
        jwt_verifier=auth.verifier,
    )
    async with app.router.lifespan_context(app):
        if request.param == "in_process":
            yield app.state.container.resolve(NotificationsApi), h  # the module's own binding
        else:

            async def token() -> str:
                return auth.service_token()

            client = ServiceHttpClient(
                "http://notifications",
                target="notifications",
                token_provider=token,
                transport=ASGITransport(app=app),
                backoff_seconds=0.001,
            )
            yield NotificationsHttpClient(client), h
            await client.aclose()


async def test_send_and_get_delivery(setup: tuple[NotificationsApi, Harness]) -> None:
    api, h = setup
    result = await api.send(otp(idempotency_key="c-1"))
    assert (result.status, result.provider, result.channel) == (
        DeliveryStatus.SENT,
        "static",
        Channel.EMAIL,
    )
    info = await api.get_delivery(result.delivery_id)
    assert info.recipient_masked == "a***@example.com" and info.status is DeliveryStatus.SENT
    assert h.static.calls == 1


async def test_failover_is_invisible_to_the_caller(setup: tuple[NotificationsApi, Harness]) -> None:
    api, h = setup
    h.static.outcome = "unavailable"
    result = await api.send(otp())
    assert (result.provider, result.attempts) == ("memory", 2)


async def test_errors_are_the_same_types_in_both_implementations(
    setup: tuple[NotificationsApi, Harness],
) -> None:
    api, h = setup
    with pytest.raises(NotificationsInvalidRequest) as bad:
        await api.send(otp("nope"))
    assert bad.value.code == "NOTIFICATIONS_INVALID_RECIPIENT"

    with pytest.raises(DeliveryNotFound):
        await api.get_delivery(uuid4())

    await api.send(otp("k@example.com", idempotency_key="same"))
    with pytest.raises(NotificationsIdempotencyConflict):
        await api.send(otp("other@example.com", idempotency_key="same"))

    h.static.outcome = "reject"
    with pytest.raises(NotificationsInvalidRequest) as rejected:
        await api.send(otp("r@example.com"))
    assert rejected.value.code == "NOTIFICATIONS_RECIPIENT_REJECTED"
    assert "delivery_id" in rejected.value.details


async def test_total_failure_and_rate_limit_are_mapped(
    setup: tuple[NotificationsApi, Harness],
) -> None:
    api, h = setup
    h.static.outcome = "unavailable"
    # the chain is static,memory: make BOTH providers unavailable
    h.memory.send = _always_down  # type: ignore[method-assign]
    with pytest.raises(NotificationsUnavailable) as down:
        await api.send(otp("x@example.com"))
    assert "delivery_id" in down.value.details

    with pytest.raises(NotificationsUnavailable):
        await api.send(otp("x@example.com"))
    with pytest.raises(NotificationsUnavailable):
        await api.send(otp("x@example.com"))
    with pytest.raises(NotificationsRateLimited) as limited:
        await api.send(otp("x@example.com"))  # the 4th within the hour (cap is 3)
    assert limited.value.retry_after_seconds and limited.value.retry_after_seconds > 0


async def _always_down(message):  # type: ignore[no-untyped-def]
    from notifications_service.application.ports import SenderUnavailable

    raise SenderUnavailable("down")
