"""In-process implementation of notifications_contracts.api (used while the service lives in the monolith)."""

from uuid import UUID

from notifications_contracts import DeliveryInfo, SendRequest, SendResult
from notifications_service.application.services.send_notification import (
    GetDelivery,
    SendNotification,
)
from platform_observability import app_service_scope, traced_contract_call

_CONTRACT = "notifications_contracts.NotificationsApi"


class NotificationsApiImpl:
    def __init__(self, send: SendNotification, get_delivery: GetDelivery) -> None:
        self._send = send
        self._get_delivery = get_delivery

    @traced_contract_call(_CONTRACT)
    async def send(self, request: SendRequest) -> SendResult:
        # In-process calls run inside the CALLER's request, so the context says app.service=<caller>.
        # Re-scope to this service so its spans, metrics and logs are attributed to it (and dashboards stay right).
        with app_service_scope("notifications"):
            return await self._send(request)

    @traced_contract_call(_CONTRACT)
    async def get_delivery(self, delivery_id: UUID) -> DeliveryInfo:
        with app_service_scope("notifications"):
            return await self._get_delivery(delivery_id)
