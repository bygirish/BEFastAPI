"""Test helpers shipped with the service (like platform_security.testing): a module on SQLite with injectable senders."""

from collections.abc import Mapping
from typing import Any

from notifications_contracts import Channel, SendRequest
from notifications_service.application.ports import Sender
from notifications_service.infrastructure.providers.memory import InMemorySender
from notifications_service.infrastructure.providers.static import StaticSender
from notifications_service.module import NotificationsModule


class Harness:
    """A module on a throw-away SQLite file with injectable senders: the service, alone, behind its own database."""

    def __init__(self, module: NotificationsModule, senders: Mapping[str, Sender]) -> None:
        self.module = module
        self.senders = senders

    @property
    def memory(self) -> InMemorySender:
        sender = self.senders["memory"]
        assert isinstance(sender, InMemorySender)
        return sender

    @property
    def static(self) -> StaticSender:
        sender = self.senders["static"]
        assert isinstance(sender, StaticSender)
        return sender


def otp(recipient: str = "Asha@Example.com", **kwargs: Any) -> SendRequest:
    return SendRequest(
        channel=kwargs.pop("channel", Channel.EMAIL),
        recipient=recipient,
        template="otp",
        variables={"code": "482913", "ttl_minutes": "5"},
        **kwargs,
    )
