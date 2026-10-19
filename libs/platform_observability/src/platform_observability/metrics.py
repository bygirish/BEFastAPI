"""Metric instruments with attribute allow-lists (rule O-5).

Every instrument declares the attribute keys it accepts (and optionally a closed set of
values). `app.service` is stamped automatically from the request/job context. Unknown
attributes raise in local/test and are dropped (not exported) elsewhere, so a typo or a
high-cardinality value can never explode series counts in production.
"""

from collections.abc import Mapping
from typing import Any

from opentelemetry import metrics

from platform_observability import context

# Latency buckets (seconds): 5 ms … 10 s (OBSERVABILITY §5.3)
LATENCY_BUCKETS_S: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

_STRICT = True


def set_strict(strict: bool) -> None:
    """Strict (raise) in local/test; lenient (drop attribute) in staging/production."""
    global _STRICT
    _STRICT = strict


AllowedAttributes = Mapping[str, frozenset[str] | None]


class MetricAttributeError(ValueError):
    pass


def _clean(allowed: AllowedAttributes, attributes: Mapping[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        if key not in allowed:
            if _STRICT:
                raise MetricAttributeError(f"Attribute '{key}' is not in the instrument allow-list")
            continue
        permitted = allowed[key]
        if permitted is not None and str(value) not in permitted:
            if _STRICT:
                raise MetricAttributeError(f"Value '{value}' not allowed for attribute '{key}'")
            cleaned[key] = "other"
            continue
        cleaned[key] = value
    if (svc := context.get_app_service()) is not None:
        cleaned["app.service"] = svc
    return cleaned


def get_meter(scope: str = "platform_observability") -> metrics.Meter:
    return metrics.get_meter(scope)


class Counter:
    def __init__(
        self,
        name: str,
        *,
        allowed: AllowedAttributes,
        description: str = "",
        unit: str = "1",
        scope: str = "app",
    ) -> None:
        self._allowed = allowed
        self._counter = get_meter(scope).create_counter(name, unit=unit, description=description)

    def add(self, value: int = 1, **attributes: Any) -> None:
        self._counter.add(value, _clean(self._allowed, attributes))


class Histogram:
    def __init__(
        self,
        name: str,
        *,
        allowed: AllowedAttributes,
        description: str = "",
        unit: str = "s",
        scope: str = "app",
    ) -> None:
        self._allowed = allowed
        self._hist = get_meter(scope).create_histogram(name, unit=unit, description=description)

    def record(self, value: float, **attributes: Any) -> None:
        self._hist.record(value, _clean(self._allowed, attributes))


class UpDownCounter:
    def __init__(
        self,
        name: str,
        *,
        allowed: AllowedAttributes,
        description: str = "",
        unit: str = "1",
        scope: str = "app",
    ) -> None:
        self._allowed = allowed
        self._counter = get_meter(scope).create_up_down_counter(
            name, unit=unit, description=description
        )

    def add(self, value: int, **attributes: Any) -> None:
        self._counter.add(value, _clean(self._allowed, attributes))
