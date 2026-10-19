"""In-memory telemetry for tests (rule T-8). OpenTelemetry providers can be installed once per
process, so `install()` is idempotent and `Telemetry.clear()` resets captured data between tests."""

from dataclasses import dataclass

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from platform_observability.setup import AppServiceSpanProcessor


@dataclass
class Telemetry:
    spans_exporter: InMemorySpanExporter
    metric_reader: InMemoryMetricReader

    def spans(self) -> list[ReadableSpan]:
        return list(self.spans_exporter.get_finished_spans())

    def span_names(self) -> list[str]:
        return [s.name for s in self.spans()]

    def metric_names(self) -> set[str]:
        data = self.metric_reader.get_metrics_data()
        if data is None:
            return set()
        return {
            metric.name
            for resource_metrics in data.resource_metrics
            for scope_metrics in resource_metrics.scope_metrics
            for metric in scope_metrics.metrics
        }

    def data_points(self, metric_name: str) -> list[dict[str, object]]:
        data = self.metric_reader.get_metrics_data()
        points: list[dict[str, object]] = []
        if data is None:
            return points
        for resource_metrics in data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == metric_name:
                        points.extend(dict(dp.attributes or {}) for dp in metric.data.data_points)
        return points

    def clear(self) -> None:
        self.spans_exporter.clear()


_telemetry: Telemetry | None = None


def install() -> Telemetry:
    global _telemetry
    if _telemetry is not None:
        return _telemetry
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(AppServiceSpanProcessor())
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)

    reader = InMemoryMetricReader()
    metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))
    _telemetry = Telemetry(spans_exporter=exporter, metric_reader=reader)
    return _telemetry
