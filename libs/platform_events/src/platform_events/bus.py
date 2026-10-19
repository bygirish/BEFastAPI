"""EventBus port and the in-process implementation (rules C-6, C-7).

Today the relay publishes outbox rows to `InProcessEventBus`; after extraction the same
relay targets a broker adapter. Producers and handlers never change.
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Protocol

from platform_events.events import IntegrationEvent
from platform_observability import get_logger, start_span

Handler = Callable[[IntegrationEvent], Awaitable[None]]


class EventDeliveryError(Exception):
    """One or more handlers failed. The relay retries; handlers are idempotent (C-7)."""

    def __init__(self, failures: dict[str, BaseException]) -> None:
        self.failures = failures
        super().__init__(f"{len(failures)} handler(s) failed: {', '.join(sorted(failures))}")


class EventBus(Protocol):
    async def publish(self, event: IntegrationEvent) -> None: ...

    def subscribe(self, event_name: str, handler: Handler, *, name: str | None = None) -> None: ...


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[tuple[str, Handler]]] = defaultdict(list)
        self._log = get_logger("events.bus")

    def subscribe(self, event_name: str, handler: Handler, *, name: str | None = None) -> None:
        handler_name = (
            name or f"{handler.__module__}.{getattr(handler, '__qualname__', repr(handler))}"
        )
        self._handlers[event_name].append((handler_name, handler))

    async def publish(self, event: IntegrationEvent) -> None:
        failures: dict[str, BaseException] = {}
        for handler_name, handler in self._handlers.get(event.event_name, []):
            try:
                with start_span(
                    f"events.handle {event.event_name}",
                    attributes={"messaging.handler": handler_name},
                ):
                    await handler(event)
            except Exception as exc:  # noqa: BLE001 - isolate handlers; aggregate and let relay retry
                failures[handler_name] = exc
                self._log.warning(
                    "event_handler_failed",
                    event_name=event.event_name,
                    event_id=str(event.event_id),
                    handler=handler_name,
                    exc_info=exc,
                )
        if failures:
            raise EventDeliveryError(failures)
