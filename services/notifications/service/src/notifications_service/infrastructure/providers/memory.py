"""DEV/TEST ONLY: remember messages in a list so tests (and the dev viewer endpoint) can look at them."""

from notifications_contracts import Channel
from notifications_service.application.ports import OutboundMessage


class InMemorySender:
    name = "memory"
    channels = frozenset(Channel)

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)

    def messages(self) -> list[OutboundMessage]:
        return list(self.sent)

    def clear(self) -> None:
        self.sent.clear()
