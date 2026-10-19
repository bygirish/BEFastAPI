from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from notifications_service.infrastructure.db.models import SCHEMA
from notifications_service.settings import NotificationsSettings
from platform_core.db import create_engine, create_session_factory


def build_engine(
    settings: NotificationsSettings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    if settings.database_url.startswith("sqlite"):
        # SQLite has no schemas: tests map the service schema to the default one.
        engine = engine.execution_options(schema_translate_map={SCHEMA: None})
    return engine, create_session_factory(engine)
