"""Idempotent handler wrapper (rule C-7): dedupe on (handler name, event_id)."""

from typing import Protocol
from uuid import UUID

from platform_events.bus import Handler
from platform_events.events import IntegrationEvent


class ProcessedEvents(Protocol):
    async def seen(self, handler: str, event_id: UUID) -> bool: ...

    async def mark(self, handler: str, event_id: UUID) -> None: ...


class InMemoryProcessedEvents:
    def __init__(self) -> None:
        self._seen: set[tuple[str, UUID]] = set()

    async def seen(self, handler: str, event_id: UUID) -> bool:
        return (handler, event_id) in self._seen

    async def mark(self, handler: str, event_id: UUID) -> None:
        self._seen.add((handler, event_id))


def idempotent(handler_name: str, store: ProcessedEvents, handler: Handler) -> Handler:
    async def wrapper(event: IntegrationEvent) -> None:
        if await store.seen(handler_name, event.event_id):
            return
        await handler(event)
        await store.mark(handler_name, event.event_id)

    return wrapper
