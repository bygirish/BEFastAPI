"""The single door every service exposes to the composition root (docs/architecture §4.2).

A service never mounts itself or touches the FastAPI app. `apps/*` calls these methods.
"""

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from fastapi import APIRouter

from platform_core.container import Container
from platform_core.health import HealthReport
from platform_events.bus import EventBus
from platform_events.outbox import OutboxStore

ENTRY_POINT_GROUP = "befastapi.services"


@runtime_checkable
class ServiceModule(Protocol):
    name: str

    def routers(self) -> Sequence[APIRouter]:
        """Routers with prefixes already applied: /api/v1/<name>/… and /internal/v1/<name>/…"""
        ...

    def provide(self, container: Container) -> None:
        """Bind this service's contract implementations (e.g. `FilesApi -> FilesApiImpl`)."""
        ...

    def bind_standalone_defaults(self, container: Container) -> None:
        """Bind fakes for ports owned by other services (single-service runs, extraction drill)."""
        ...

    def register_event_handlers(self, bus: EventBus) -> None: ...

    def outbox_store(self) -> OutboxStore | None: ...

    async def on_startup(self, container: Container) -> None: ...

    async def on_shutdown(self) -> None: ...

    async def health(self) -> HealthReport: ...


class BaseServiceModule:
    """Convenient defaults; services override what they need."""

    name: str

    def routers(self) -> Sequence[APIRouter]:
        return ()

    def provide(self, container: Container) -> None:
        return None

    def bind_standalone_defaults(self, container: Container) -> None:
        return None

    def register_event_handlers(self, bus: EventBus) -> None:
        return None

    def outbox_store(self) -> OutboxStore | None:
        return None

    async def on_startup(self, container: Container) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def health(self) -> HealthReport:
        return HealthReport(service=self.name)


_PUBLIC_PREFIX = r"/api/v[0-9]+/{name}"
_INTERNAL_PREFIX = r"/internal/v[0-9]+/{name}"


def validate_router_prefix(module_name: str, router: APIRouter) -> None:
    """Enforce gateway-routable prefixes (docs/architecture §12)."""
    pattern = re.compile(
        rf"^(?:{_PUBLIC_PREFIX.format(name=module_name)}|{_INTERNAL_PREFIX.format(name=module_name)})(?:/.*)?$"
    )
    if not pattern.match(router.prefix):
        raise ValueError(
            f"Router prefix {router.prefix!r} of service {module_name!r} must be "
            f"/api/v<N>/{module_name}… or /internal/v<N>/{module_name}…"
        )
