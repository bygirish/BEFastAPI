"""FastAPI dependencies. This layer is the only one allowed to use Depends (rule L-6)."""

from typing import Annotated

from fastapi import Depends, Request

from notifications_service.application.ports import SentMessageLog
from notifications_service.application.services.send_notification import (
    GetDelivery,
    SendNotification,
)
from platform_core.errors import ForbiddenError
from platform_security import CurrentPrincipal, Principal, PrincipalKind


def get_send(request: Request) -> SendNotification:
    use_case: SendNotification = request.app.state.container.resolve(SendNotification)
    return use_case


def get_get_delivery(request: Request) -> GetDelivery:
    use_case: GetDelivery = request.app.state.container.resolve(GetDelivery)
    return use_case


def get_message_log(request: Request) -> SentMessageLog | None:
    container = request.app.state.container
    log: SentMessageLog | None = (
        container.resolve(SentMessageLog) if container.is_bound(SentMessageLog) else None
    )
    return log


SendUseCase = Annotated[SendNotification, Depends(get_send)]
GetDeliveryUseCase = Annotated[GetDelivery, Depends(get_get_delivery)]
MessageLog = Annotated[SentMessageLog | None, Depends(get_message_log)]


async def require_service_principal(principal: CurrentPrincipal) -> Principal:
    """Internal routes are for other services only (rule X-9)."""
    if principal.kind is not PrincipalKind.SERVICE:
        raise ForbiddenError("Internal endpoint")
    return principal
