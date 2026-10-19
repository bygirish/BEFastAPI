"""Outbox relay: moves committed outbox rows to the EventBus (rules D-5, O-6)."""

import asyncio
import contextlib

from opentelemetry.trace import SpanKind

from platform_events.bus import EventBus
from platform_events.events import event_type_for
from platform_events.outbox import DrainStats, OutboxMessage, OutboxStore
from platform_observability import Counter, get_logger, link_from_traceparent, start_span
from platform_observability.context import app_service_scope

_published = Counter(
    "events.outbox.published",
    allowed={"event": None, "outcome": frozenset({"ok", "retry", "dead"})},
    description="Outbox messages processed by the relay",
    scope="platform_events",
)


class OutboxRelay:
    def __init__(
        self,
        service: str,
        store: OutboxStore,
        bus: EventBus,
        *,
        interval_seconds: float = 0.5,
        batch_size: int = 100,
        max_attempts: int = 10,
    ) -> None:
        self._service = service
        self._store = store
        self._bus = bus
        self._interval = interval_seconds
        self._batch = batch_size
        self._max_attempts = max_attempts
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._log = get_logger("events.relay")

    async def _publish(self, message: OutboxMessage) -> None:
        event = event_type_for(message.event_name).model_validate(message.payload)
        links = link_from_traceparent(message.traceparent)
        with start_span(
            f"events.publish {message.event_name}",
            kind=SpanKind.PRODUCER,
            attributes={"messaging.message.id": str(message.id), "messaging.operation": "publish"},
            links=links,
        ):
            await self._bus.publish(event)

    async def run_once(self) -> DrainStats:
        with app_service_scope(self._service):
            stats = await self._store.drain(
                self._publish, limit=self._batch, max_attempts=self._max_attempts
            )
            if stats.published:
                _published.add(stats.published, event="all", outcome="ok")
            if stats.failed:
                _published.add(stats.failed, event="all", outcome="retry")
            if stats.dead:
                _published.add(stats.dead, event="all", outcome="dead")
                self._log.error("outbox_dead_lettered", count=stats.dead, service=self._service)
            return stats

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except Exception:  # noqa: BLE001 - the relay must survive transient DB errors (rule O-11)
                self._log.exception("outbox_relay_iteration_failed", service=self._service)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)

    def start(self) -> None:
        if self._task is None:
            self._stopping.clear()
            self._task = asyncio.create_task(self._loop(), name=f"outbox-relay-{self._service}")

    async def stop(self) -> None:
        if self._task is not None:
            self._stopping.set()
            await self._task
            self._task = None
            await self.run_once()  # final flush
