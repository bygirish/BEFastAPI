from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest

from notifications_service.application.ports import Sender
from notifications_service.infrastructure.db.models import metadata
from notifications_service.infrastructure.providers.memory import InMemorySender
from notifications_service.infrastructure.providers.static import StaticSender
from notifications_service.module import NotificationsModule
from notifications_service.settings import NotificationsSettings
from notifications_service.testing import Harness
from platform_observability import testing as obs_testing
from platform_security.testing import TestAuth


@pytest.fixture(scope="session", autouse=True)
def telemetry() -> obs_testing.Telemetry:
    return obs_testing.install()


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


MakeHarness = Callable[..., Any]


@pytest.fixture
async def make_harness(tmp_path: Path) -> AsyncIterator[MakeHarness]:
    created: list[NotificationsModule] = []

    async def factory(*, email: str = "memory", sms: str = "memory", **overrides: Any) -> Harness:
        settings = NotificationsSettings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/notifications-{len(created)}.db",
            email_providers=email,
            sms_providers=sms,
            **overrides,
        )
        senders: dict[str, Sender] = {"memory": InMemorySender(), "static": StaticSender("accept")}
        module = NotificationsModule(settings, senders=senders)
        async with module.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        created.append(module)
        return Harness(module, senders)

    yield factory
    for module in created:
        await module.engine.dispose()
