from typing import ClassVar
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from platform_core.db import create_session_factory, make_metadata
from platform_events import (
    EventDeliveryError,
    InMemoryOutbox,
    InMemoryProcessedEvents,
    InProcessEventBus,
    IntegrationEvent,
    OutboxRelay,
    SqlOutboxStore,
    SqlOutboxWriter,
    event_type_for,
    idempotent,
    make_outbox_table,
)
from platform_events.events import InvalidEventDefinitionError


class ThingHappened(IntegrationEvent):
    EVENT_NAME: ClassVar[str] = "tests.thing_happened.v1"
    thing_id: UUID


def new_event() -> ThingHappened:
    return ThingHappened(thing_id=UUID(int=1))


def test_event_name_must_follow_convention() -> None:
    with pytest.raises(InvalidEventDefinitionError):

        class Bad(IntegrationEvent):
            EVENT_NAME: ClassVar[str] = "BadName"

    assert event_type_for("tests.thing_happened.v1") is ThingHappened
    with pytest.raises(LookupError):
        event_type_for("tests.unknown_thing.v1")


async def test_bus_aggregates_handler_failures_and_isolates_handlers() -> None:
    bus = InProcessEventBus()
    seen: list[str] = []

    async def ok(event: IntegrationEvent) -> None:
        seen.append("ok")

    async def boom(event: IntegrationEvent) -> None:
        raise RuntimeError("nope")

    bus.subscribe(ThingHappened.EVENT_NAME, boom, name="boom")
    bus.subscribe(ThingHappened.EVENT_NAME, ok, name="ok")
    with pytest.raises(EventDeliveryError) as info:
        await bus.publish(new_event())
    assert seen == ["ok"]  # failure of one handler does not block others
    assert set(info.value.failures) == {"boom"}


async def test_idempotent_handler_runs_once() -> None:
    calls = 0

    async def handler(event: IntegrationEvent) -> None:
        nonlocal calls
        calls += 1

    wrapped = idempotent("h", InMemoryProcessedEvents(), handler)
    event = new_event()
    await wrapped(event)
    await wrapped(event)
    assert calls == 1


async def test_relay_publishes_retries_and_dead_letters() -> None:
    outbox = InMemoryOutbox()
    bus = InProcessEventBus()
    attempts = 0

    async def flaky(event: IntegrationEvent) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("transient")

    bus.subscribe(ThingHappened.EVENT_NAME, flaky, name="flaky")
    await outbox.add(new_event())
    relay = OutboxRelay("tests", outbox, bus, max_attempts=3)

    first = await relay.run_once()
    assert (first.published, first.failed) == (0, 1)
    second = await relay.run_once()
    assert second.published == 1
    assert await outbox.pending_count() == 0

    # poison message ends up dead-lettered after max_attempts
    async def always_fails(event: IntegrationEvent) -> None:
        raise RuntimeError("poison")

    bus2 = InProcessEventBus()
    bus2.subscribe(ThingHappened.EVENT_NAME, always_fails, name="poison")
    outbox2 = InMemoryOutbox()
    await outbox2.add(new_event())
    relay2 = OutboxRelay("tests", outbox2, bus2, max_attempts=2)
    await relay2.run_once()
    last = await relay2.run_once()
    assert last.dead == 1
    assert outbox2.messages[0].failed_at is not None


async def test_sql_outbox_roundtrip_with_relay() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    metadata = make_metadata(None)
    table = make_outbox_table(metadata)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    sessions = create_session_factory(engine)

    async with sessions() as session, session.begin():
        await SqlOutboxWriter(session, table).add(new_event())  # same transaction as business data

    received: list[IntegrationEvent] = []

    async def handler(event: IntegrationEvent) -> None:
        received.append(event)

    bus = InProcessEventBus()
    bus.subscribe(ThingHappened.EVENT_NAME, handler, name="collect")
    store = SqlOutboxStore(sessions, table)
    assert await store.pending_count() == 1
    stats = await OutboxRelay("tests", store, bus).run_once()
    assert stats.published == 1 and await store.pending_count() == 0
    assert isinstance(received[0], ThingHappened)
    await engine.dispose()
