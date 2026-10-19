"""The single door used by the composition root (docs/architecture §4.2)."""

from collections.abc import Mapping, Sequence

from fastapi import APIRouter
from sqlalchemy import text

from notifications_contracts import NotificationsApi
from notifications_service.api.dev.router import router as dev_router
from notifications_service.api.internal.router import router as internal_router
from notifications_service.application.gateway import NotificationGateway
from notifications_service.application.ports import Sender, SentMessageLog
from notifications_service.application.services.send_notification import (
    DeliveryPolicy,
    GetDelivery,
    SendNotification,
)
from notifications_service.application.telemetry import prime_metrics
from notifications_service.contracts_impl import NotificationsApiImpl
from notifications_service.infrastructure.db.engine import build_engine
from notifications_service.infrastructure.db.models import outbox_table
from notifications_service.infrastructure.db.uow import SqlUnitOfWork
from notifications_service.infrastructure.providers.memory import InMemorySender
from notifications_service.infrastructure.providers.registry import build_chains, build_senders
from notifications_service.settings import NotificationsSettings
from platform_core.clock import SystemClock
from platform_core.container import Container
from platform_core.health import CheckResult, HealthReport, HealthStatus
from platform_events import OutboxStore, SqlOutboxStore
from platform_http import BaseServiceModule


class NotificationsModule(BaseServiceModule):
    name = "notifications"

    def __init__(
        self,
        settings: NotificationsSettings | None = None,
        *,
        senders: Mapping[str, Sender] | None = None,
    ) -> None:
        self.settings = (
            settings or NotificationsSettings()
        )  # validates the production guard (rule X-11)
        # DB spans come from the global SQLAlchemy instrumentation installed by platform_observability.setup(),
        # which therefore must run BEFORE the module (and its engine) is constructed.
        self.engine, self.sessions = build_engine(self.settings)
        self._store = SqlOutboxStore(self.sessions, outbox_table)
        # Tests may inject their own senders; production builds them from the configured provider names.
        self.senders: Mapping[str, Sender] = senders or build_senders(self.settings)

    def routers(self) -> Sequence[APIRouter]:
        routers = [internal_router]  # no public routes: other services call us, users never do
        if self.settings.dev_endpoints:
            routers.append(dev_router)
        return routers

    def provide(self, container: Container) -> None:
        s = self.settings
        chains = build_chains(s, self.senders)
        gateway = NotificationGateway(chains, attempt_timeout_seconds=s.attempt_timeout_seconds)
        prime_metrics(
            {channel.value: [sender.name for sender in chain] for channel, chain in chains.items()}
        )
        policy = DeliveryPolicy(
            pepper=s.digest_pepper.get_secret_value().encode(),
            rate_limit_per_hour=s.rate_limit_per_hour,
        )
        uow_factory = lambda: SqlUnitOfWork(self.sessions)  # noqa: E731
        send = SendNotification(uow_factory, gateway, SystemClock(), policy)
        get_delivery = GetDelivery(uow_factory)
        container.bind(SendNotification, send)
        container.bind(GetDelivery, get_delivery)
        container.bind(NotificationsApi, NotificationsApiImpl(send, get_delivery))
        memory = self.senders.get("memory")
        if isinstance(memory, InMemorySender):
            container.bind(SentMessageLog, memory)

    def outbox_store(self) -> OutboxStore | None:
        return self._store

    async def on_shutdown(self) -> None:
        await self.engine.dispose()

    async def health(self) -> HealthReport:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            check = CheckResult(name="database")
        except Exception as exc:  # noqa: BLE001 - readiness must report, not raise
            check = CheckResult(
                name="database", status=HealthStatus.DOWN, detail=type(exc).__name__
            )
        return HealthReport.from_checks(self.name, [check])


def build_module() -> NotificationsModule:
    """Entry point registered under `befastapi.services` (pyproject)."""
    return NotificationsModule()
