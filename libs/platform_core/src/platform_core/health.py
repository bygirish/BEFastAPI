"""Health model aggregated by /readyz (rule O-10)."""

from enum import StrEnum

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


_SEVERITY = {HealthStatus.OK: 0, HealthStatus.DEGRADED: 1, HealthStatus.DOWN: 2}


def worst(statuses: list[HealthStatus]) -> HealthStatus:
    return max(statuses, key=_SEVERITY.__getitem__, default=HealthStatus.OK)


class CheckResult(BaseModel):
    name: str
    status: HealthStatus = HealthStatus.OK
    detail: str | None = None


class HealthReport(BaseModel):
    service: str
    status: HealthStatus = HealthStatus.OK
    checks: list[CheckResult] = Field(default_factory=list)

    @classmethod
    def from_checks(cls, service: str, checks: list[CheckResult]) -> "HealthReport":
        return cls(service=service, status=worst([c.status for c in checks]), checks=checks)
