import httpx
import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from platform_core.errors import (
    ConflictError,
    DependencyTimeoutError,
    NotFoundError,
    RateLimitedError,
    UnavailableError,
)
from platform_http import ServiceHttpClient, install_error_handlers, validate_router_prefix


class Body(BaseModel):
    n: int


def make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/missing")
    async def missing() -> None:
        raise NotFoundError("nope", code="DEMO_THING_NOT_FOUND")

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError()

    @app.get("/limited")
    async def limited() -> None:
        raise RateLimitedError(retry_after_seconds=7)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    @app.post("/validate")
    async def validate(body: Body) -> Body:
        return body

    return app


async def test_uniform_error_body_and_status_mapping() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=make_app(), raise_app_exceptions=False), base_url="http://t"
    ) as c:
        missing = await c.get("/missing")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "DEMO_THING_NOT_FOUND"
        assert (await c.get("/conflict")).status_code == 409
        limited = await c.get("/limited")
        assert limited.status_code == 429 and limited.headers["retry-after"] == "7"
        invalid = await c.post("/validate", json={"n": "x"})
        assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "INVALID_INPUT"
        boom = await c.get("/boom")
        assert boom.status_code == 500
        assert "secret internals" not in boom.text  # never leak internals
        assert (await c.get("/nope")).json()["error"]["code"] == "NOT_FOUND"


async def test_client_retries_idempotent_requests_then_maps_errors() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls < 3 else httpx.Response(200, json={"ok": True})

    client = ServiceHttpClient(
        "http://svc", target="files", backoff_seconds=0, transport=httpx.MockTransport(handler)
    )
    assert (await client.request("GET", "/x")).json() == {"ok": True}
    assert calls == 3

    calls = 0
    post_client = ServiceHttpClient(
        "http://svc",
        target="files",
        backoff_seconds=0,
        transport=httpx.MockTransport(lambda r: httpx.Response(503)),
    )
    with pytest.raises(UnavailableError):  # POST without idempotency key is never retried
        await post_client.request("POST", "/x", json={})

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    slow = ServiceHttpClient(
        "http://svc", target="files", backoff_seconds=0, transport=httpx.MockTransport(timeout)
    )
    with pytest.raises(DependencyTimeoutError):
        await slow.request("GET", "/x")


def test_router_prefix_validation() -> None:
    validate_router_prefix("auth", APIRouter(prefix="/api/v1/auth"))
    validate_router_prefix("auth", APIRouter(prefix="/internal/v1/auth/users"))
    with pytest.raises(ValueError):
        validate_router_prefix("auth", APIRouter(prefix="/api/v1/users"))
    with pytest.raises(ValueError):
        validate_router_prefix("auth", APIRouter(prefix="/auth"))


async def test_exhausted_retryable_status_keeps_the_remote_error_body() -> None:
    body = {
        "error": {
            "code": "THING_DOWN",
            "message": "nope",
            "details": {"id": "7"},
            "request_id": "r",
        }
    }
    client = ServiceHttpClient(
        "http://svc",
        target="svc",
        transport=httpx.MockTransport(lambda r: httpx.Response(503, json=body)),
    )
    with pytest.raises(UnavailableError) as info:
        await client.request("POST", "/x")
    assert info.value.details["status"] == 503
    assert info.value.details["remote_error"]["code"] == "THING_DOWN"
    assert info.value.details["remote_error"]["details"] == {"id": "7"}
    await client.aclose()
