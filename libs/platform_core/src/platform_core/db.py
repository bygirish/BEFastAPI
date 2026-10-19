"""Async SQLAlchemy helpers. One schema per service, one engine per service (rules D-1, D-3)."""

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def make_metadata(schema: str | None) -> MetaData:
    """Metadata bound to the owning service's schema (None only for tests on SQLite)."""
    return MetaData(schema=schema, naming_convention=NAMING_CONVENTION)


def create_engine(
    url: str, *, echo: bool = False, pool_size: int = 5, max_overflow: int = 5
) -> AsyncEngine:
    if url.startswith("sqlite"):
        return create_async_engine(url, echo=echo)
    return create_async_engine(
        url, echo=echo, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
