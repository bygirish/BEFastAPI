"""Composition tests with fake modules: no real service is required for the root to be verified."""

from collections.abc import Sequence

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from monolith_app.settings import MonolithSettings
from platform_core.container import Container
from platform_core.health import HealthReport, HealthStatus
from platform_events import InMemoryOutbox, IntegrationEvent, OutboxStore
from platform_http import BaseServiceModule, ServiceModule, create_application


class FakeModule(BaseServiceModule):
    name = "fake"

    def __init__(self, status: HealthStatus = HealthStatus.OK) -> None:
        self._status = status
        self.started = False
        self.stopped = False
        self.outbox = InMemoryOutbox()
        self.seen: list[IntegrationEvent] = []

    def routers(self) -> Sequence[APIRouter]:
        router = APIRouter(prefix="/api/v1/fake")

        @router.get("/hello")
        async def hello() -> dict[str, str]:
            return {"hello": "world"}

        return [router]

    def outbox_store(self) -> OutboxStore | None:
        return self.outbox

    async def on_startup(self, container: Container) -> None:
        self.started = True

    async def on_shutdown(self) -> None:
        self.stopped = True

    async def health(self) -> HealthReport:
        return HealthReport(service=self.name, status=self._status)


class BadPrefixModule(FakeModule):
    def routers(self) -> Sequence[APIRouter]:
        return [APIRouter(prefix="/not-namespaced")]


def build(module: ServiceModule) -> object:
    return create_application(title="t", service_name="t", modules=[module], telemetry=False)


async def test_lifecycle_routes_and_health() -> None:
    module = FakeModule()
    app = create_application(title="t", service_name="t", modules=[module], telemetry=False)
    async with app.router.lifespan_context(app):
        assert module.started
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            assert (await client.get("/api/v1/fake/hello")).json() == {"hello": "world"}
            ready = await client.get("/readyz")
            assert ready.status_code == 200 and ready.json()["modules"][0]["service"] == "fake"
            assert (await client.get("/livez")).status_code == 200
    assert module.stopped


async def test_not_ready_until_started_and_when_a_module_is_down() -> None:
    app = create_application(
        title="t", service_name="t", modules=[FakeModule(HealthStatus.DOWN)], telemetry=False
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/readyz")).status_code == 503  # before startup
        assert (await client.get("/startupz")).status_code == 503
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            assert (await client.get("/startupz")).status_code == 200
            assert (await client.get("/readyz")).status_code == 503  # module reports DOWN


def test_router_prefix_is_enforced_at_composition_time() -> None:
    with pytest.raises(ValueError):
        build(BadPrefixModule())


def test_enabled_services_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLED_SERVICES", "auth, users ,files")
    assert MonolithSettings().enabled_services == ["auth", "users", "files"]
    monkeypatch.delenv("ENABLED_SERVICES")
    assert MonolithSettings().enabled_services == []


async def test_one_server_span_and_no_duplicate_request_metric() -> None:
    """FastAPI ships its own OpenTelemetry. We keep its spans but disable its metrics/logs so the RED metric
    exists exactly once and always carries app.service (regression test for double-counting)."""
    from platform_observability import testing as obs_testing

    telemetry = obs_testing.install()
    telemetry.clear()
    app = create_application(title="t", service_name="t", modules=[FakeModule()], telemetry=False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            assert (await client.get("/api/v1/fake/hello")).status_code == 200

    servers = [s for s in telemetry.spans() if s.kind.name == "SERVER"]
    assert len(servers) == 1
    # The in-memory metric reader is shared by the whole test process: look only at THIS test's route.
    points = [
        p
        for p in telemetry.data_points("http.server.request.duration")
        if p.get("http.route") == "/api/v1/fake/hello"
    ]
    assert points
    assert all(p.get("app.service") == "fake" for p in points)


class ExplodingModule(FakeModule):
    name = "boom"

    def routers(self) -> Sequence[APIRouter]:
        router = APIRouter(prefix="/api/v1/boom")

        @router.get("/now")
        async def now() -> None:
            raise RuntimeError("secret internals")

        return [router]


async def test_unhandled_errors_still_carry_the_request_id_and_leak_nothing() -> None:
    """Regression (found by the 'Postgres is down' drill): the 500 body used to say request_id=null."""
    app = create_application(
        title="t", service_name="t", modules=[ExplodingModule()], telemetry=False
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            response = await client.get(
                "/api/v1/boom/now", headers={"x-request-id": "req-abcdefgh"}
            )
    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "INTERNAL_ERROR"
    assert body["request_id"] == "req-abcdefgh" == response.headers["x-request-id"]
    assert "secret internals" not in response.text
