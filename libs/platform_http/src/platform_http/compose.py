"""Application factory shared by every composition root (apps/monolith, apps/<svc>_api).

It is generic plumbing: discover service modules, mount their routers, wire the event bus and
outbox relays, expose health, install error handling and observability. It knows nothing about
any particular service (rule B-3), and services are found through entry points, so adding a
service never edits this code (rule B-4: only `apps/*` decides what is wired together).
"""

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from importlib.metadata import entry_points

from fastapi import FastAPI

from platform_core.container import Container
from platform_core.health import HealthReport
from platform_core.settings import PlatformSettings
from platform_events.bus import EventBus, InProcessEventBus
from platform_events.relay import OutboxRelay
from platform_http.errors import install_error_handlers
from platform_http.module import ENTRY_POINT_GROUP, ServiceModule, validate_router_prefix
from platform_observability import (
    ObservabilityHandle,
    ObservabilityMiddleware,
    build_health_router,
    get_logger,
    instrument_app,
    setup,
)

Wiring = Callable[[Container, Sequence[ServiceModule]], None]


def load_modules(enabled: Sequence[str] | None = None) -> list[ServiceModule]:
    """Instantiate modules registered under the `befastapi.services` entry-point group."""
    available = {ep.name: ep for ep in entry_points(group=ENTRY_POINT_GROUP)}
    names = list(enabled) if enabled else sorted(available)
    unknown = [n for n in names if n not in available]
    if unknown:
        raise LookupError(f"Unknown service(s) {unknown}; installed: {sorted(available)}")
    modules: list[ServiceModule] = []
    for name in names:
        module = available[name].load()()
        if not isinstance(module, ServiceModule):
            raise TypeError(f"Entry point {name!r} did not return a ServiceModule")
        modules.append(module)
    return modules


def create_application(
    *,
    title: str,
    service_name: str,
    modules: Sequence[ServiceModule],
    wiring: Wiring | None = None,
    standalone: bool = False,
    platform_settings: PlatformSettings | None = None,
    telemetry: bool = True,
    observability: ObservabilityHandle | None = None,
    jwt_verifier: object | None = None,
    permission_resolver: object | None = None,
    relay_interval_seconds: float = 0.5,
) -> FastAPI:
    settings = platform_settings or PlatformSettings()
    log = get_logger("compose")
    # Prefer calling setup() yourself BEFORE building modules (so their DB engines are traced).
    obs = (
        observability
        if observability is not None
        else (setup(settings, service_name=service_name) if telemetry else None)
    )

    container = Container()
    bus = InProcessEventBus()
    container.bind(EventBus, bus)
    started = False
    relays: list[OutboxRelay] = []

    for module in modules:
        module.provide(container)
    if standalone:
        for module in modules:
            module.bind_standalone_defaults(container)
    if wiring is not None:
        wiring(container, modules)
    for module in modules:
        module.register_event_handlers(bus)

    async def readiness() -> list[HealthReport]:
        return [await module.health() for module in modules]

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        nonlocal started
        started_modules: list[ServiceModule] = []
        try:
            for module in modules:
                await module.on_startup(container)
                started_modules.append(module)
                if (store := module.outbox_store()) is not None:
                    relay = OutboxRelay(
                        module.name, store, bus, interval_seconds=relay_interval_seconds
                    )
                    relay.start()
                    relays.append(relay)
            started = True
            log.info(
                "application_started", services=[m.name for m in modules], standalone=standalone
            )
            yield
        finally:
            started = False
            for relay in relays:
                await relay.stop()
            relays.clear()
            for module in reversed(started_modules):
                await module.on_shutdown()
            if obs is not None:
                obs.shutdown()

    app = FastAPI(title=title, lifespan=lifespan)
    app.state.container = container
    app.state.event_bus = bus
    if jwt_verifier is not None:
        app.state.jwt_verifier = jwt_verifier
    if permission_resolver is not None:
        app.state.permission_resolver = permission_resolver

    install_error_handlers(app)
    app.include_router(build_health_router(readiness=readiness, started=lambda: started))
    for module in modules:
        for router in module.routers():
            validate_router_prefix(module.name, router)
            app.include_router(router)

    app.add_middleware(ObservabilityMiddleware, known_services={m.name for m in modules})
    if telemetry:
        instrument_app(app)  # must come after add_middleware so the server span is outermost
    return app


__all__ = ["Wiring", "create_application", "load_modules"]
