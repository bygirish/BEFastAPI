"""ASGI middleware: request id, app.service stamping, access log, RED metric (rules O-2, O-7, O-12)."""

import re
import time
from collections.abc import Iterable

from opentelemetry import trace
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from platform_core.ids import uuid7
from platform_observability import context
from platform_observability.logging import get_logger
from platform_observability.metrics import LATENCY_BUCKETS_S, Histogram  # noqa: F401

REQUEST_ID_HEADER = "x-request-id"
_SERVICE_PATH = re.compile(r"^/(?:api|internal)/v\d+/([a-z][a-z0-9_]*)(?:/|$)")
_MAX_REQUEST_ID = 128

_http_duration = Histogram(
    "http.server.request.duration",
    allowed={
        "http.request.method": None,
        "http.route": None,
        "http.response.status_code": None,
    },
    description="Duration of inbound HTTP requests",
    unit="s",
    scope="platform_observability.http",
)


def service_from_path(path: str, known: frozenset[str]) -> str | None:
    match = _SERVICE_PATH.match(path)
    if match and match.group(1) in known:
        return match.group(1)
    return None


class ObservabilityMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        known_services: Iterable[str] = (),
        quiet_paths: Iterable[str] = ("/livez", "/readyz", "/startupz"),
    ) -> None:
        self.app = app
        self.known = frozenset(known_services)
        self.quiet = frozenset(quiet_paths)
        self._log = get_logger("http.access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        raw_id = headers.get(REQUEST_ID_HEADER, "")
        request_id = (
            raw_id[:_MAX_REQUEST_ID]
            if re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", raw_id)
            else str(uuid7())
        )
        path: str = scope["path"]
        service = service_from_path(path, self.known)

        rid_token = context.set_request_id(request_id)
        svc_token = context.set_app_service(service)
        context.bind_principal(None, None)

        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("request_id", request_id)
            if service:
                span.set_attribute("app.service", service)

        status_code = 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - started
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            method: str = scope["method"]
            if path not in self.quiet:
                _http_duration.record(
                    duration,
                    **{
                        "http.request.method": method,
                        "http.route": route,
                        "http.response.status_code": status_code,
                    },
                )
                self._log.info(
                    "http_request_completed",
                    **{
                        "http.request.method": method,
                        "http.route": route,
                        "http.response.status_code": status_code,
                        "duration_ms": round(duration * 1000, 2),
                    },
                )
            context.reset_app_service(svc_token)
            context.reset_request_id(rid_token)
