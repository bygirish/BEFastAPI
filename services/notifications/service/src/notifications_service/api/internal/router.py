"""/internal/v1/notifications/… mirrors notifications_contracts.api 1:1; called by NotificationsHttpClient after extraction."""

from uuid import UUID

from fastapi import APIRouter, Depends

from notifications_contracts import DeliveryInfo, SendRequest, SendResult
from notifications_service.api.deps import (
    GetDeliveryUseCase,
    SendUseCase,
    require_service_principal,
)

router = APIRouter(
    prefix="/internal/v1/notifications",
    tags=["notifications-internal"],
    dependencies=[Depends(require_service_principal)],
    include_in_schema=False,
)


@router.post("/send", response_model=SendResult)
async def send(request: SendRequest, use_case: SendUseCase) -> SendResult:
    return await use_case(request)


@router.get("/deliveries/{delivery_id}", response_model=DeliveryInfo)
async def get_delivery(delivery_id: UUID, use_case: GetDeliveryUseCase) -> DeliveryInfo:
    return await use_case(delivery_id)
