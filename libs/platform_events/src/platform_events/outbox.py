"""Transactional outbox (rule D-5).

Write side: `OutboxWriter.add(event)` runs inside the use case's unit of work, so the data
change and the event are committed atomically.
Read side: `OutboxStore.drain()` is used by the relay; it claims pending rows, publishes them,
and marks them published / failed / dead-lettered.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from platform_events.events import IntegrationEvent
from platform_observability import current_traceparent


@dataclass
class OutboxMessage:
    id: UUID
    event_name: str
    payload: dict[str, Any]
    traceparent: str | None
    created_at: datetime
    attempts: int = 0
    published_at: datetime | None = None
    failed_at: datetime | None = None
    last_error: str | None = None


@dataclass
class DrainStats:
    published: int = 0
    failed: int = 0
    dead: int = 0


Publish = Callable[[OutboxMessage], Awaitable[None]]


class OutboxWriter(Protocol):
    async def add(self, event: IntegrationEvent) -> None: ...


class OutboxStore(Protocol):
    async def drain(
        self, publish: Publish, *, limit: int = 100, max_attempts: int = 10
    ) -> DrainStats: ...

    async def pending_count(self) -> int: ...


def _to_message(event: IntegrationEvent) -> OutboxMessage:
    return OutboxMessage(
        id=event.event_id,
        event_name=event.event_name,
        payload=event.model_dump(mode="json"),
        traceparent=current_traceparent(),
        created_at=datetime.now(UTC),
    )


# ------------------------------------------------------------------ in-memory (tests, fakes)
class InMemoryOutbox:
    """Implements both OutboxWriter and OutboxStore."""

    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    async def add(self, event: IntegrationEvent) -> None:
        self.messages.append(_to_message(event))

    async def pending_count(self) -> int:
        return sum(1 for m in self.messages if m.published_at is None and m.failed_at is None)

    async def drain(
        self, publish: Publish, *, limit: int = 100, max_attempts: int = 10
    ) -> DrainStats:
        stats = DrainStats()
        pending = [m for m in self.messages if m.published_at is None and m.failed_at is None][
            :limit
        ]
        for message in pending:
            try:
                await publish(message)
            except Exception as exc:  # noqa: BLE001 - recorded on the row, retried later
                message.attempts += 1
                message.last_error = f"{type(exc).__name__}: {exc}"[:500]
                if message.attempts >= max_attempts:
                    message.failed_at = datetime.now(UTC)
                    stats.dead += 1
                else:
                    stats.failed += 1
            else:
                message.published_at = datetime.now(UTC)
                stats.published += 1
        return stats


# ------------------------------------------------------------------ SQLAlchemy
def make_outbox_table(metadata: MetaData, name: str = "outbox") -> Table:
    """Create the outbox table inside a service's own metadata/schema."""
    payload_type = JSON().with_variant(JSONB(), "postgresql")
    return Table(
        name,
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("event_name", String(200), nullable=False),
        Column("payload", payload_type, nullable=False),
        Column("traceparent", String(64)),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("published_at", DateTime(timezone=True)),
        Column("attempts", Integer, nullable=False, server_default="0"),
        Column("failed_at", DateTime(timezone=True)),
        Column("last_error", Text),
    )


class SqlOutboxWriter:
    """Bound to the unit-of-work session so the insert commits with the business data."""

    def __init__(self, session: AsyncSession, table: Table) -> None:
        self._session = session
        self._table = table

    async def add(self, event: IntegrationEvent) -> None:
        message = _to_message(event)
        await self._session.execute(
            insert(self._table).values(
                id=message.id,
                event_name=message.event_name,
                payload=message.payload,
                traceparent=message.traceparent,
                created_at=message.created_at,
            )
        )


class SqlOutboxStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], table: Table) -> None:
        self._session_factory = session_factory
        self._table = table

    async def pending_count(self) -> int:
        t = self._table
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(t)
                .where(t.c.published_at.is_(None), t.c.failed_at.is_(None))
            )
            return int(result.scalar_one())

    async def drain(
        self, publish: Publish, *, limit: int = 100, max_attempts: int = 10
    ) -> DrainStats:
        t = self._table
        stats = DrainStats()
        async with self._session_factory() as session, session.begin():
            rows = (
                (
                    await session.execute(
                        select(t)
                        .where(t.c.published_at.is_(None), t.c.failed_at.is_(None))
                        .order_by(t.c.created_at, t.c.id)
                        .limit(limit)
                        .with_for_update(
                            skip_locked=True
                        )  # multiple relays never double-claim (ignored on SQLite)
                    )
                )
                .mappings()
                .all()
            )
            for row in rows:
                message = OutboxMessage(
                    id=row["id"],
                    event_name=row["event_name"],
                    payload=row["payload"],
                    traceparent=row["traceparent"],
                    created_at=row["created_at"],
                    attempts=row["attempts"],
                )
                try:
                    await publish(message)
                except Exception as exc:  # noqa: BLE001 - recorded on the row, retried later
                    attempts = message.attempts + 1
                    dead = attempts >= max_attempts
                    await session.execute(
                        update(t)
                        .where(t.c.id == message.id)
                        .values(
                            attempts=attempts,
                            last_error=f"{type(exc).__name__}: {exc}"[:500],
                            failed_at=datetime.now(UTC) if dead else None,
                        )
                    )
                    stats.dead += int(dead)
                    stats.failed += int(not dead)
                else:
                    await session.execute(
                        update(t).where(t.c.id == message.id).values(published_at=datetime.now(UTC))
                    )
                    stats.published += 1
        return stats
