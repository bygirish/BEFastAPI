"""OpenTelemetry SDK bootstrap (rules O-1, O-11). Only this module touches SDK/exporters.

Configuration follows the standard OTEL_* environment variables so ops can change behaviour
without code changes. ``OTEL_SDK_DISABLED=true`` turns every signal into a no-op while
stdout JSON logging keeps working.
"""

import importlib
import importlib.util
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from platform_core.settings import PlatformSettings
from platform_observability import context
from platform_observability.logging import configure_logging, json_formatter
from platform_observability.metrics import LATENCY_BUCKETS_S, set_strict


class AppServiceSpanProcessor(SpanProcessor):
    """Stamps `app.service` on every span started inside a service context (rule O-7)."""

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        service = context.get_app_service()
        if service is not None:
            span.set_attribute("app.service", service)

    def on_end(self, span: ReadableSpan) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


@dataclass
class ObservabilityHandle:
    """Returned by setup(); call shutdown() on application stop to flush exporters."""

    enabled: bool
    _providers: list[Any] = field(default_factory=list)
    _log_handler: logging.Handler | None = None

    def shutdown(self) -> None:
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
        for provider in self._providers:
            try:
                provider.shutdown()
            except Exception:
                logging.getLogger(__name__).warning("telemetry_shutdown_failed", exc_info=True)


# Attributes structlog's ProcessorFormatter puts on the LogRecord; OpenTelemetry would try to export them as
# attributes and log a warning ("Invalid type ... for attribute value") for every single line.
_STRUCTLOG_RECORD_ATTRS = frozenset(
    {"_logger", "_name", "msg", "args", "exc_info", "exc_text", "stack_info"}
)


class _SafeLoggingHandler(LoggingHandler):
    """OTLP log handler: ships our one-line JSON as the log body and can never take the app down (rule O-11).

    Two things the live docker-compose run taught us:
      * the record's `msg` is a structlog event dict. We render it ONCE with our JSON formatter and hand OpenTelemetry a
        clean record whose message is that string (formatting twice crashed start-up with AttributeError);
      * `emit` runs inline in business code, so any exporter error is swallowed via `handleError`.
    """

    def __init__(
        self, logger_provider: LoggerProvider, json_formatter: logging.Formatter | None
    ) -> None:
        super().__init__(level=logging.NOTSET, logger_provider=logger_provider)
        self._json_formatter = json_formatter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            rendered = (
                self._json_formatter.format(record) if self._json_formatter else record.getMessage()
            )
            clean = logging.makeLogRecord(
                {k: v for k, v in record.__dict__.items() if k not in _STRUCTLOG_RECORD_ATTRS}
            )
            clean.msg, clean.args = rendered, ()
            super().emit(clean)
        except Exception:  # noqa: BLE001 - telemetry must never raise into the caller
            self.handleError(record)


def build_log_handler(
    logger_provider: LoggerProvider, formatter: logging.Formatter | None
) -> logging.Handler:
    return _SafeLoggingHandler(logger_provider, formatter)


def setup(
    settings: PlatformSettings | None = None,
    *,
    service_name: str,
    service_namespace: str = "befastapi",
    instance_id: str | None = None,
) -> ObservabilityHandle:
    """Configure logging always; configure OTLP export unless OTEL_SDK_DISABLED=true."""
    settings = settings or PlatformSettings()
    set_strict(settings.env in ("local", "test"))
    configure_logging(
        level=settings.log_level,
        service_name=service_name,
        version=settings.app_version,
        env=settings.env,
    )

    if os.environ.get("OTEL_SDK_DISABLED", "false").lower() == "true":
        return ObservabilityHandle(enabled=False)

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
            "service.namespace": service_namespace,
            "service.version": settings.app_version,
            "service.instance.id": instance_id or os.environ.get("HOSTNAME", "local"),
            "deployment.environment.name": settings.env,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(AppServiceSpanProcessor())
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True))
        ],
        views=[
            View(
                instrument_name="*duration*",
                aggregation=ExplicitBucketHistogramAggregation(LATENCY_BUCKETS_S),
            )
        ],
    )
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
    )
    set_logger_provider(logger_provider)
    root = logging.getLogger()
    handler = build_log_handler(logger_provider, json_formatter())
    root.addHandler(handler)

    HTTPXClientInstrumentor().instrument()
    _instrument_optional()
    return ObservabilityHandle(
        enabled=True,
        _providers=[tracer_provider, meter_provider, logger_provider],
        _log_handler=handler,
    )


# (library to look for, instrumentor module, instrumentor class)
_OPTIONAL_INSTRUMENTORS: tuple[tuple[str, str, str], ...] = (
    ("sqlalchemy", "opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor"),
    ("redis", "opentelemetry.instrumentation.redis", "RedisInstrumentor"),
)


def _instrument_optional() -> None:
    """Instrument SQLAlchemy/Redis globally, but ONLY if the library is installed in this environment.

    The production image installs just what the services declare (no dev group), so e.g. `redis` may be absent
    until a service needs it; importing its instrumentor unconditionally would crash start-up (found by the
    docker-compose stack check). Engines/clients created after setup() are traced, hence setup() must run before
    service modules build their engines."""
    for library, module_name, class_name in _OPTIONAL_INSTRUMENTORS:
        if importlib.util.find_spec(library) is None:
            continue
        instrumentor = getattr(importlib.import_module(module_name), class_name)
        instrumentor().instrument()
