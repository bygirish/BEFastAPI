from datetime import UTC, datetime
from typing import Protocol

import pytest

from platform_core import (
    Container,
    FixedClock,
    HealthReport,
    HealthStatus,
    NotBoundError,
    PlatformSettings,
    uuid7,
)
from platform_core.health import CheckResult
from platform_core.pagination import Page, PageRequest


def test_uuid7_is_version7_and_time_ordered() -> None:
    first, second = uuid7(), uuid7()
    assert first.version == 7
    assert first.variant == "specified in RFC 4122"
    assert first != second
    assert (first.int >> 80) <= (second.int >> 80)


def test_fixed_clock_requires_tz_and_advances() -> None:
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance(seconds=30)
    assert clock.now().second == 30
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 1, 1))


class Greeter(Protocol):
    def greet(self) -> str: ...


class English:
    def greet(self) -> str:
        return "hello"


def test_container_bind_resolve_and_override() -> None:
    container = Container()
    with pytest.raises(NotBoundError):
        container.resolve(Greeter)
    container.bind(Greeter, English())
    assert container.resolve(Greeter).greet() == "hello"
    with pytest.raises(ValueError):
        container.bind(Greeter, English())
    container.bind(Greeter, English(), override=True)
    container.bind_default(Greeter, English())  # no-op when already bound
    assert container.is_bound(Greeter)


def test_health_report_takes_worst_status() -> None:
    report = HealthReport.from_checks(
        "demo",
        [CheckResult(name="db"), CheckResult(name="redis", status=HealthStatus.DEGRADED)],
    )
    assert report.status is HealthStatus.DEGRADED
    assert HealthReport.from_checks("demo", []).status is HealthStatus.OK


def test_settings_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    settings = PlatformSettings()
    assert settings.is_production
    assert settings.app_version == "1.2.3"


def test_page_defaults() -> None:
    assert PageRequest().limit == 50
    assert Page[int](items=[1, 2]).next_cursor is None
