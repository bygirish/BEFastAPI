"""Use cases: send a templated message through the gateway, and look a delivery up.

Shape of `send` (and why the database transaction is NOT held open during the provider call):

    tx 1  idempotency check + rate limit + INSERT delivery(status=pending)        commit
          ── provider call(s), seconds long, no transaction, no row locks ──
    tx 2  UPDATE delivery(sent|failed) [+ outbox event on failure]                commit

Trade-off, stated honestly: if the process dies between the provider accepting the message and tx 2, the row
stays `pending` although the message went out; a retry with the same idempotency key would send again.
That is *at-least-once* delivery — the right side to err on for OTP/transactional mail.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from notifications_contracts import (
    DeliveryFailed,
    DeliveryInfo,
    DeliveryNotFound,
    DeliveryStatus,
    NotificationsIdempotencyConflict,
    NotificationsInvalidRequest,
    NotificationsRateLimited,
    NotificationsUnavailable,
    SendRequest,
    SendResult,
)
from notifications_service.application.gateway import GatewayResult, NotificationGateway
from notifications_service.application.ports import DuplicateKey, OutboundMessage, UnitOfWork
from notifications_service.application.telemetry import DELIVERIES, RATE_LIMITED
from notifications_service.domain.delivery import Delivery
from notifications_service.domain.errors import NotificationsDomainError
from notifications_service.domain.recipients import (
    mask_recipient,
    normalise_recipient,
    recipient_digest,
)
from notifications_service.domain.templates import render
from platform_core.clock import Clock
from platform_core.ids import uuid7
from platform_observability import get_logger, traced_use_case

_WINDOW = timedelta(hours=1)
REJECTED_CODE = "NOTIFICATIONS_RECIPIENT_REJECTED"
ALL_PROVIDERS_FAILED_CODE = "NOTIFICATIONS_ALL_PROVIDERS_FAILED"
NO_PROVIDER_CODE = "NOTIFICATIONS_NO_PROVIDER_CONFIGURED"


@dataclass(frozen=True)
class DeliveryPolicy:
    pepper: bytes
    rate_limit_per_hour: int


def _result(delivery: Delivery) -> SendResult:
    return SendResult(
        delivery_id=delivery.id,
        status=delivery.status,
        channel=delivery.channel,
        provider=delivery.provider,
        attempts=delivery.attempts,
    )


class SendNotification:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        gateway: NotificationGateway,
        clock: Clock,
        policy: DeliveryPolicy,
    ) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway
        self._clock = clock
        self._policy = policy
        self._log = get_logger("notifications.send")

    @traced_use_case
    async def __call__(self, request: SendRequest) -> SendResult:
        try:
            recipient = normalise_recipient(request.channel, request.recipient)
            rendered = render(request.template, request.channel, request.variables)
        except NotificationsDomainError as exc:
            raise NotificationsInvalidRequest(
                exc.message, code=exc.code, details=exc.details
            ) from exc
        digest = recipient_digest(self._policy.pepper, request.channel, recipient)

        delivery, replay = await self._open(request, recipient, digest)
        if replay:
            return _result(delivery)

        result = await self._gateway.deliver(
            OutboundMessage(request.channel, recipient, rendered.subject, rendered.body)
        )
        return await self._close(delivery, result)

    # ---- tx 1 -------------------------------------------------------------------------------------------
    async def _open(
        self, request: SendRequest, recipient: str, digest: str
    ) -> tuple[Delivery, bool]:
        key = request.idempotency_key
        now = self._clock.now()
        async with self._uow_factory() as uow:
            if key is not None:
                existing = await uow.deliveries.find_by_key(key)
                if existing is not None:
                    return await self._reuse(uow, existing, request, digest)

            # Approximate on purpose: count-then-insert is not atomic, so a burst of parallel requests can slip a few
            # past the cap. It stops floods (SMS pumping), not exact counts; an exact cap needs an atomic counter.
            recent = await uow.deliveries.created_since(digest, now - _WINDOW)
            if len(recent) >= self._policy.rate_limit_per_hour:
                RATE_LIMITED.add(channel=request.channel.value)
                wait = math.ceil((recent[0] + _WINDOW - now).total_seconds())
                raise NotificationsRateLimited(retry_after_seconds=max(wait, 1))

            delivery = Delivery(
                id=uuid7(),
                channel=request.channel,
                recipient_masked=mask_recipient(request.channel, recipient),
                recipient_digest=digest,
                template=request.template,
                created_at=now,
                updated_at=now,
                idempotency_key=key,
            )
            try:
                await uow.deliveries.add(delivery)
                await uow.commit()
            except DuplicateKey as exc:  # lost a race with a request carrying the same key
                raise NotificationsIdempotencyConflict(
                    "A request with this idempotency key is already in flight."
                ) from exc
        return delivery, False

    async def _reuse(
        self, uow: UnitOfWork, existing: Delivery, request: SendRequest, digest: str
    ) -> tuple[Delivery, bool]:
        if (
            existing.recipient_digest != digest
            or existing.template != request.template
            or existing.channel is not request.channel
        ):
            raise NotificationsIdempotencyConflict()
        if existing.status is DeliveryStatus.SENT:
            return existing, True  # the whole point of the key: same answer, nothing sent twice
        if existing.status is DeliveryStatus.PENDING:
            raise NotificationsIdempotencyConflict("This delivery is still in flight.")
        existing.reopen(self._clock.now())  # it FAILED before: the retry deserves a real attempt
        await uow.deliveries.update(existing)
        await uow.commit()
        return existing, False

    # ---- tx 2 -------------------------------------------------------------------------------------------
    async def _close(self, delivery: Delivery, result: GatewayResult) -> SendResult:
        now = self._clock.now()
        channel = delivery.channel.value
        count = len(result.attempts)
        if result.sent and result.provider is not None:
            delivery.mark_sent(provider=result.provider, attempts=count, now=now)
            async with self._uow_factory() as uow:
                await uow.deliveries.update(delivery)
                await uow.commit()
            DELIVERIES.add(channel=channel, outcome="sent")
            self._log.info(
                "delivery_sent",
                delivery_id=str(delivery.id),
                channel=channel,
                provider=result.provider,
                attempts=count,
                recipient=delivery.recipient_masked,
            )
            return _result(delivery)

        rejected = result.rejected
        code = (
            REJECTED_CODE
            if rejected
            else (ALL_PROVIDERS_FAILED_CODE if count else NO_PROVIDER_CODE)
        )
        delivery.mark_failed(error_code=code, attempts=count, now=now)
        async with self._uow_factory() as uow:
            await uow.deliveries.update(delivery)
            await uow.outbox.add(
                DeliveryFailed(
                    delivery_id=delivery.id,
                    channel=delivery.channel,
                    template=delivery.template,
                    error_code=code,
                )
            )  # same transaction as the status change (rule D-5)
            await uow.commit()
        DELIVERIES.add(channel=channel, outcome="rejected" if rejected else "failed")
        self._log.warning(
            "delivery_failed",
            delivery_id=str(delivery.id),
            channel=channel,
            error_code=code,
            attempts=count,
            providers=[a.provider for a in result.attempts],
            recipient=delivery.recipient_masked,
        )
        details = {"delivery_id": str(delivery.id), "attempts": count}
        if rejected:
            raise NotificationsInvalidRequest(
                "The provider rejected this recipient.", code=code, details=details
            )
        raise NotificationsUnavailable(
            "No provider could deliver the message.", code=code, details=details
        )


class GetDelivery:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    @traced_use_case
    async def __call__(self, delivery_id: UUID) -> DeliveryInfo:
        async with self._uow_factory() as uow:
            delivery = await uow.deliveries.get(delivery_id)
        if delivery is None:
            raise DeliveryNotFound(details={"delivery_id": str(delivery_id)})
        return DeliveryInfo(
            delivery_id=delivery.id,
            channel=delivery.channel,
            recipient_masked=delivery.recipient_masked,
            template=delivery.template,
            status=delivery.status,
            provider=delivery.provider,
            attempts=delivery.attempts,
            error_code=delivery.error_code,
            created_at=delivery.created_at,
        )
