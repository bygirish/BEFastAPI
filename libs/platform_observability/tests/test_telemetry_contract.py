"""Telemetry contract test (T-8): a request yields spans, correlated logs and RED metrics
carrying app.service; metric attributes are allow-listed."""

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from platform_observability import (
    Counter,
    ObservabilityMiddleware,
    app_service_scope,
    configure_logging,
    get_logger,
    traced_use_case,
)
from platform_observability import testing as obs_testing
from platform_observability.metrics import MetricAttributeError, set_strict


class DoThing:
    @traced_use_case
    async def __call__(self) -> str:
        get_logger("usecase").info("thing_done")
        return "done"


def make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/demo/ping")
    async def ping() -> dict[str, str]:
        return {"result": await DoThing()()}

    app.add_middleware(ObservabilityMiddleware, known_services={"demo"})
    return app


async def test_request_produces_correlated_signals(capsys: pytest.CaptureFixture[str]) -> None:
    telemetry = obs_testing.install()
    telemetry.clear()
    configure_logging(level="INFO", service_name="contract-test", env="test")

    async with AsyncClient(transport=ASGITransport(app=make_app()), base_url="http://t") as client:
        response = await client.get("/api/v1/demo/ping", headers={"x-request-id": "req-12345678"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-12345678"
    assert "demo.DoThing" in telemetry.span_names()
    use_case_span = next(s for s in telemetry.spans() if s.name == "demo.DoThing")
    assert (
        use_case_span.attributes is not None and use_case_span.attributes["app.service"] == "demo"
    )

    points = telemetry.data_points("http.server.request.duration")
    assert any(
        p.get("app.service") == "demo" and p.get("http.route") == "/api/v1/demo/ping"
        for p in points
    )

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    done = next(line for line in lines if line["event"] == "thing_done")
    assert done["request_id"] == "req-12345678"
    assert done["app.service"] == "demo"
    assert len(done["trace_id"]) == 32


def test_metric_attribute_allow_list() -> None:
    obs_testing.install()
    counter = Counter(
        "demo.logins", allowed={"method": frozenset({"password", "otp"}), "outcome": None}
    )
    with app_service_scope("demo"):
        counter.add(method="password", outcome="success")
    set_strict(True)
    with pytest.raises(MetricAttributeError):
        counter.add(user_id="u-1")
    with pytest.raises(MetricAttributeError):
        counter.add(method="carrier-pigeon")
    set_strict(False)
    counter.add(user_id="u-1", method="carrier-pigeon")  # dropped / bucketed, never raises in prod
    set_strict(True)
