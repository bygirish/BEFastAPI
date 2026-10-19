"""Module-level tests: the service works alone, behind its own database (rules B-6, T-2)."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from notifications_service.domain.templates import TEMPLATES
from notifications_service.module import NotificationsModule
from notifications_service.settings import NotificationsSettings
from notifications_service.testing import Harness
from platform_http import create_application
from platform_security.testing import TestAuth


async def client_for(h: Harness, auth: TestAuth) -> tuple[AsyncClient, object]:
    app = create_application(
        title="t",
        service_name="notifications-tests",
        modules=[h.module],
        telemetry=False,
        jwt_verifier=auth.verifier,
        relay_interval_seconds=0.05,
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t"), app


async def test_internal_routes_require_a_service_principal(
    make_harness: Any, auth: TestAuth
) -> None:
    h: Harness = await make_harness()
    client, app = await client_for(h, auth)
    body = {"channel": "email", "recipient": "a@example.com", "template": "password_changed"}
    async with app.router.lifespan_context(app), client:  # type: ignore[attr-defined]
        assert (await client.post("/internal/v1/notifications/send", json=body)).status_code == 401
        assert (
            await client.post("/internal/v1/notifications/send", json=body, headers=auth.headers())
        ).status_code == 403
        ok = await client.post(
            "/internal/v1/notifications/send", json=body, headers=auth.service_headers()
        )
        assert ok.status_code == 200 and ok.json()["status"] == "sent"
        # the uniform error body for a bad request, including the request id
        bad = await client.post(
            "/internal/v1/notifications/send",
            json={**body, "recipient": "not-an-email"},
            headers=auth.service_headers(),
        )
        assert (
            bad.status_code == 422
            and bad.json()["error"]["code"] == "NOTIFICATIONS_INVALID_RECIPIENT"
        )


async def test_there_are_no_public_or_dev_routes_by_default(
    make_harness: Any, auth: TestAuth
) -> None:
    h: Harness = await make_harness()
    client, app = await client_for(h, auth)
    async with app.router.lifespan_context(app), client:  # type: ignore[attr-defined]
        assert (await client.post("/api/v1/notifications/dev/send", json={})).status_code == 404
        paths = app.openapi()["paths"]  # type: ignore[attr-defined]
        assert not any(
            "notifications" in p for p in paths
        )  # internal routes are hidden from the public schema


async def test_dev_endpoints_send_and_show_what_the_memory_sender_captured(
    make_harness: Any, auth: TestAuth
) -> None:
    h: Harness = await make_harness(dev_endpoints=True)
    client, app = await client_for(h, auth)
    async with app.router.lifespan_context(app), client:  # type: ignore[attr-defined]
        sent = await client.post(
            "/api/v1/notifications/dev/send",
            json={"channel": "email", "recipient": "dev@example.com"},
        )
        assert sent.status_code == 200 and sent.json()["provider"] == "memory"
        messages = (await client.get("/api/v1/notifications/dev/messages")).json()
        assert messages[0]["to"] == "dev@example.com" and "123456" in messages[0]["body"]
        wrong = await client.post(
            "/api/v1/notifications/dev/send",
            json={"channel": "pigeon", "recipient": "not-an-email"},
        )
        assert (
            wrong.status_code == 422
            and wrong.json()["error"]["code"] == "NOTIFICATIONS_INVALID_CHANNEL"
        )


async def test_a_production_module_with_dev_settings_cannot_be_built() -> None:
    with pytest.raises(ValidationError, match="refusing to start in production"):
        NotificationsModule(NotificationsSettings(env="production", email_providers="console"))


async def test_readiness_reports_database(make_harness: Any, auth: TestAuth) -> None:
    h: Harness = await make_harness()
    client, app = await client_for(h, auth)
    async with app.router.lifespan_context(app), client:  # type: ignore[attr-defined]
        body = (await client.get("/readyz")).json()
        assert body["modules"][0]["checks"][0] == {
            "name": "database",
            "status": "ok",
            "detail": None,
        }


async def test_dev_send_fills_sample_variables_for_every_builtin_template(
    make_harness: Any, auth: TestAuth
) -> None:
    """Regression (found in the live run): defaults were OTP-only, so `password_changed` and `welcome` returned 422."""
    h: Harness = await make_harness(dev_endpoints=True)
    client, app = await client_for(h, auth)
    async with app.router.lifespan_context(app), client:  # type: ignore[attr-defined]
        for template in TEMPLATES:
            response = await client.post(
                "/api/v1/notifications/dev/send",
                json={"channel": "sms", "recipient": "+14155550123", "template": template},
            )
            assert response.status_code == 200, (template, response.text)
