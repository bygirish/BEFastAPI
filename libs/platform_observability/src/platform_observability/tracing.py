"""Tracing helpers (rule O-6): use-case spans, contract-call spans, event context propagation."""

import functools
import inspect
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import propagate, trace
from opentelemetry.trace import Link, Span, SpanKind, Status, StatusCode

from platform_core.errors import CLIENT_ERROR_TYPES
from platform_observability import context

_TRACER_NAME = "platform_observability"


def get_tracer(name: str = _TRACER_NAME) -> trace.Tracer:
    return trace.get_tracer(name)


def record_failure(span: Span, exc: BaseException) -> None:
    """Record an exception. Caller mistakes (4xx) do not mark the span as failed."""
    span.record_exception(exc)
    if not isinstance(exc, CLIENT_ERROR_TYPES):
        span.set_status(Status(StatusCode.ERROR, str(exc)[:200]))


@contextmanager
def start_span(
    name: str,
    *,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
    links: list[Link] | None = None,
) -> Iterator[Span]:
    attrs = dict(attributes or {})
    if (svc := context.get_app_service()) is not None:
        attrs.setdefault("app.service", svc)
    with get_tracer().start_as_current_span(
        name,
        kind=kind,
        attributes=attrs,
        links=links,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except BaseException as exc:
            record_failure(span, exc)
            raise


def traced_use_case[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Wrap an async use-case callable. Span name: ``<app.service>.<ClassName>``."""
    if not inspect.iscoroutinefunction(func):
        raise TypeError("traced_use_case only supports async callables")

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        owner = (
            type(args[0]).__name__ if args and hasattr(args[0], "__dict__") else func.__qualname__
        )
        service = context.get_app_service() or "app"
        with start_span(f"{service}.{owner}", attributes={"code.function": func.__qualname__}):
            return await func(*args, **kwargs)

    return wrapper


def traced_contract_call(
    contract: str,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """CLIENT span at the adapter seam; same name in-process and over HTTP (rule O-6)."""

    def decorator[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with start_span(
                f"{contract}.{func.__name__}",
                kind=SpanKind.CLIENT,
                attributes={
                    "rpc.system": "contract",
                    "rpc.service": contract,
                    "rpc.method": func.__name__,
                },
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------- context propagation
def current_traceparent() -> str | None:
    """W3C traceparent of the current span, or None if there is no valid span."""
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier.get("traceparent")


def link_from_traceparent(traceparent: str | None) -> list[Link]:
    if not traceparent:
        return []
    ctx = propagate.extract({"traceparent": traceparent})
    span_context = trace.get_current_span(ctx).get_span_context()
    return [Link(span_context)] if span_context.is_valid else []


def detach_root() -> object:
    """Start a new trace root (used by the outbox relay: async work is linked, not parented)."""
    return otel_context.attach(otel_context.Context())
