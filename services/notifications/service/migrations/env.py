"""Alembic environment for the notifications service only (rule D-3): own history, own version table,
own schema. Never touches another service's schema."""

import asyncio
import os

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from notifications_service.infrastructure.db.models import SCHEMA, metadata

config = context.config


def database_url() -> str:
    url = os.environ.get("NOTIFICATIONS_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Set NOTIFICATIONS_DATABASE_URL")
    return url


def configure(connection: Connection | None, url: str | None = None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_object=lambda obj, name, type_, reflected, compare_to: (
            getattr(obj, "schema", SCHEMA) == SCHEMA if type_ == "table" else True
        ),
        literal_binds=connection is None,
        dialect_opts={"paramstyle": "named"} if connection is None else {},
    )


def run_offline() -> None:
    configure(None, url=database_url())
    with context.begin_transaction():
        context.run_migrations()


def do_run(connection: Connection) -> None:
    exists = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"), {"s": SCHEMA}
    ).first()
    if exists is None:  # normally pre-created with the right owner by the db-provision job
        connection.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
    # End the transaction that the queries above auto-started. If it stays open, Alembic sees "already in a
    # transaction", does not manage it, and the connection closing at the end ROLLS BACK every migration
    # (the job exits 0 but the tables never appear).
    connection.commit()
    configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(database_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
