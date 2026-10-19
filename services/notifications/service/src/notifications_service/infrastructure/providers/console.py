"""DEV ONLY: "send" by writing the message to the application log. Shows OTPs in plain text on purpose (rule X-11)."""

from notifications_contracts import Channel
from notifications_service.application.ports import OutboundMessage
from platform_observability import get_logger


class ConsoleSender:
    name = "console"
    channels = frozenset(Channel)

    def __init__(self) -> None:
        self._log = get_logger("notifications.console")

    async def send(self, message: OutboundMessage) -> None:
        self._log.info(
            "console_message",
            channel=message.channel.value,
            to=message.recipient,
            subject=message.subject,
            message_body=message.body,
        )
