"""DEVELOPMENT ONLY. Mounted by the module solely when NOTIFICATIONS_DEV_ENDPOINTS=true, which the settings
refuse in production (rule X-11). Lets you fire a message with curl and look at what the memory sender captured."""

from fastapi import APIRouter

from notifications_contracts import Channel, SendRequest
from notifications_service.api.deps import MessageLog, SendUseCase
from notifications_service.api.dev.schemas import DevMessage, DevSendRequest, DevSendResponse
from platform_core.errors import InvalidInputError

# Sample variables so `curl -d '{"channel":"email","recipient":"a@b.co","template":"welcome"}'` just works.
SAMPLE_VARIABLES: dict[str, dict[str, str]] = {
    "otp": {"code": "123456", "ttl_minutes": "5"},
    "welcome": {"name": "Dev"},
}

router = APIRouter(prefix="/api/v1/notifications/dev", tags=["notifications-dev"])


@router.post("/send", response_model=DevSendResponse)
async def dev_send(body: DevSendRequest, use_case: SendUseCase) -> DevSendResponse:
    try:
        channel = Channel(body.channel)
    except ValueError as exc:
        raise InvalidInputError(
            "channel must be 'sms' or 'email'", code="NOTIFICATIONS_INVALID_CHANNEL"
        ) from exc
    result = await use_case(
        SendRequest(
            channel=channel,
            recipient=body.recipient,
            template=body.template,
            variables=SAMPLE_VARIABLES.get(body.template, {})
            if body.variables is None
            else body.variables,
            idempotency_key=body.idempotency_key,
        )
    )
    return DevSendResponse(
        delivery_id=str(result.delivery_id),
        status=result.status.value,
        provider=result.provider,
        attempts=result.attempts,
    )


@router.get("/messages", response_model=list[DevMessage])
async def dev_messages(log: MessageLog) -> list[DevMessage]:
    """Messages captured by the 'memory' provider (empty when it is not in any chain)."""
    if log is None:
        return []
    return [
        DevMessage(channel=m.channel.value, to=m.recipient, subject=m.subject, body=m.body)
        for m in log.messages()
    ]
