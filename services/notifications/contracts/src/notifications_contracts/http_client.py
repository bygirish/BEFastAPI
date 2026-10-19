"""HTTP implementation of the contract, used after the service is extracted (docs/architecture §6.1)."""

from uuid import UUID

import httpx

from notifications_contracts.dto import DeliveryInfo, SendRequest, SendResult
from notifications_contracts.errors import (
    DeliveryNotFound,
    NotificationsIdempotencyConflict,
    NotificationsInvalidRequest,
    NotificationsRateLimited,
    NotificationsUnavailable,
)
from platform_core.errors import UnavailableError
from platform_http import ServiceHttpClient
from platform_observability import traced_contract_call

_CONTRACT = "notifications_contracts.NotificationsApi"


def _unavailable(exc: UnavailableError) -> NotificationsUnavailable:
    """Retries were exhausted on a 502/503/504: keep the remote service's own code and details when it sent them."""
    remote = exc.details.get("remote_error") or {}
    return NotificationsUnavailable(
        remote.get("message") or exc.message,
        code=remote.get("code"),
        details={**(remote.get("details") or {}), "status": exc.details.get("status")},
    )


def _raise_for(response: httpx.Response) -> None:
    """Turn the uniform error body back into the exact exception the in-process implementation raises."""
    if response.status_code < 400:
        return
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    message, code, details = error.get("message"), error.get("code"), error.get("details")
    match response.status_code:
        case 404:
            raise DeliveryNotFound(message, code=code, details=details)
        case 409:
            raise NotificationsIdempotencyConflict(message, code=code, details=details)
        case 422:
            raise NotificationsInvalidRequest(message, code=code, details=details)
        case 429:
            retry_after = response.headers.get("Retry-After")
            raise NotificationsRateLimited(
                message,
                code=code,
                details=details,
                retry_after_seconds=int(retry_after) if retry_after else None,
            )
        case _:
            raise NotificationsUnavailable(
                message, code=code, details={**(details or {}), "status": response.status_code}
            )


class NotificationsHttpClient:
    def __init__(self, client: ServiceHttpClient) -> None:
        self._client = client

    @traced_contract_call(_CONTRACT)
    async def send(self, request: SendRequest) -> SendResult:
        try:
            response = await self._client.request(
                "POST",
                "/internal/v1/notifications/send",
                json=request.model_dump(mode="json"),
                # With a key the client may safely retry transport failures: the service de-duplicates.
                idempotency_key=request.idempotency_key,
            )
        except UnavailableError as exc:
            raise _unavailable(exc) from exc
        _raise_for(response)
        return SendResult.model_validate(response.json())

    @traced_contract_call(_CONTRACT)
    async def get_delivery(self, delivery_id: UUID) -> DeliveryInfo:
        try:
            response = await self._client.request(
                "GET", f"/internal/v1/notifications/deliveries/{delivery_id}"
            )
        except UnavailableError as exc:
            raise _unavailable(exc) from exc
        _raise_for(response)
        return DeliveryInfo.model_validate(response.json())
