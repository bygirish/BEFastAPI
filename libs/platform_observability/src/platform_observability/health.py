"""/livez, /readyz, /startupz (rule O-10)."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response
from pydantic import BaseModel

from platform_core.health import HealthReport, HealthStatus, worst

ReadinessProbe = Callable[[], Awaitable[list[HealthReport]]]


class ReadinessBody(BaseModel):
    status: HealthStatus
    modules: list[HealthReport]


def build_health_router(*, readiness: ReadinessProbe, started: Callable[[], bool]) -> APIRouter:
    router = APIRouter(tags=["health"], include_in_schema=False)

    @router.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/startupz")
    async def startupz(response: Response) -> dict[str, str]:
        if not started():
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz(response: Response) -> ReadinessBody:
        reports = await readiness() if started() else []
        status = worst([r.status for r in reports]) if started() else HealthStatus.DOWN
        if status is HealthStatus.DOWN:
            response.status_code = 503
        return ReadinessBody(status=status, modules=reports)

    return router
