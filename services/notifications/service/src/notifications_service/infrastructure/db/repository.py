from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from notifications_contracts import Channel, DeliveryStatus
from notifications_service.application.ports import DuplicateKey
from notifications_service.domain.delivery import Delivery
from notifications_service.infrastructure.db.models import deliveries_table as t


def _utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; PostgreSQL hands back aware ones. Always give the code aware UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _values(d: Delivery) -> dict[str, Any]:
    return {
        "channel": d.channel.value,
        "recipient_masked": d.recipient_masked,
        "recipient_digest": d.recipient_digest,
        "template": d.template,
        "status": d.status.value,
        "provider": d.provider,
        "attempts": d.attempts,
        "error_code": d.error_code,
        "idempotency_key": d.idempotency_key,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


def _entity(row: sa.RowMapping) -> Delivery:
    return Delivery(
        id=row["id"],
        channel=Channel(row["channel"]),
        recipient_masked=row["recipient_masked"],
        recipient_digest=row["recipient_digest"],
        template=row["template"],
        status=DeliveryStatus(row["status"]),
        provider=row["provider"],
        attempts=row["attempts"],
        error_code=row["error_code"],
        idempotency_key=row["idempotency_key"],
        created_at=_utc(row["created_at"]),
        updated_at=_utc(row["updated_at"]),
    )


class SqlDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, delivery: Delivery) -> None:
        try:
            await self._session.execute(sa.insert(t).values(id=delivery.id, **_values(delivery)))
            await self._session.flush()
        except IntegrityError as exc:  # the only unique constraint besides the primary key
            raise DuplicateKey(delivery.idempotency_key) from exc

    async def update(self, delivery: Delivery) -> None:
        await self._session.execute(
            sa.update(t).where(t.c.id == delivery.id).values(**_values(delivery))
        )

    async def get(self, delivery_id: UUID) -> Delivery | None:
        row = (
            (await self._session.execute(sa.select(t).where(t.c.id == delivery_id)))
            .mappings()
            .first()
        )
        return _entity(row) if row else None

    async def find_by_key(self, key: str) -> Delivery | None:
        row = (
            (await self._session.execute(sa.select(t).where(t.c.idempotency_key == key)))
            .mappings()
            .first()
        )
        return _entity(row) if row else None

    async def created_since(self, digest: str, since: datetime) -> list[datetime]:
        rows = await self._session.execute(
            sa.select(t.c.created_at)
            .where(t.c.recipient_digest == digest, t.c.created_at >= since)
            .order_by(t.c.created_at)
        )
        return [_utc(value) for value in rows.scalars()]
