"""Shared kernel. Technical, business-agnostic primitives only (rule B-8)."""

from platform_core.clock import Clock, FixedClock, SystemClock
from platform_core.container import Container, NotBoundError
from platform_core.errors import (
    AppError,
    ConflictError,
    DependencyTimeoutError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    UnavailableError,
)
from platform_core.health import CheckResult, HealthReport, HealthStatus
from platform_core.ids import uuid7
from platform_core.settings import PlatformSettings, ServiceSettings

__all__ = [
    "AppError",
    "CheckResult",
    "Clock",
    "ConflictError",
    "Container",
    "DependencyTimeoutError",
    "FixedClock",
    "ForbiddenError",
    "HealthReport",
    "HealthStatus",
    "InvalidInputError",
    "NotBoundError",
    "NotFoundError",
    "PlatformSettings",
    "RateLimitedError",
    "ServiceSettings",
    "SystemClock",
    "UnauthenticatedError",
    "UnavailableError",
    "uuid7",
]
