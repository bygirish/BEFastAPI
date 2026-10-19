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
        max_backoff_seconds: float = 30.0,
    ) -> None:
        self._service = service
        self._store = store
        self._bus = bus
        self._interval = interval_seconds
        self._batch = batch_size
        self._max_attempts = max_attempts
        self._max_backoff = max_backoff_seconds
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

    def _delay_after(self, consecutive_failures: int) -> float:
        """Normal interval when healthy; doubling (capped) while the store keeps failing."""
        if consecutive_failures == 0:
            return self._interval
        return float(min(self._interval * (2**consecutive_failures), self._max_backoff))

    async def _loop(self) -> None:
        failures = 0
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except Exception:  # noqa: BLE001 - the relay must survive transient DB errors (rule O-11)
                failures += 1
                if (
                    failures == 1
                ):  # one full traceback, then short reminders (no log storm while the DB is down)
                    self._log.exception("outbox_relay_iteration_failed", service=self._service)
                else:
                    self._log.warning(
                        "outbox_relay_still_failing",
                        service=self._service,
                        consecutive_failures=failures,
                        retry_in_seconds=self._delay_after(failures),
                    )
            else:
                if failures:
                    self._log.info(
                        "outbox_relay_recovered", service=self._service, after_failures=failures
                    )
                failures = 0
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self._delay_after(failures))

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
