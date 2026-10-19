"""Observability platform library. See docs/architecture/OBSERVABILITY.md."""

from platform_observability.context import app_service_scope, bind_principal, get_request_id
from platform_observability.health import build_health_router
from platform_observability.logging import configure_logging, get_logger
from platform_observability.metrics import Counter, Histogram, UpDownCounter
from platform_observability.middleware import ObservabilityMiddleware
from platform_observability.setup import (
    ObservabilityHandle,
    instrument_app,
    setup,
)
from platform_observability.tracing import (
    current_traceparent,
    link_from_traceparent,
    start_span,
    traced_contract_call,
    traced_use_case,
)

__all__ = [
    "Counter",
    "Histogram",
    "ObservabilityHandle",
    "ObservabilityMiddleware",
    "UpDownCounter",
    "app_service_scope",
    "bind_principal",
    "build_health_router",
    "configure_logging",
    "current_traceparent",
    "get_logger",
    "get_request_id",
    "instrument_app",
    "link_from_traceparent",
    "setup",
    "start_span",
    "traced_contract_call",
    "traced_use_case",
]
