"""Email over SMTP (stdlib only). Locally this talks to Mailpit (http://localhost:8025 shows what arrived).

smtplib is blocking, so each send runs in a worker thread; the socket timeout bounds that thread even when the
gateway's own timeout has already given up waiting for it.
"""

import asyncio
import smtplib
from email.message import EmailMessage

from notifications_contracts import Channel
from notifications_service.application.ports import (
    OutboundMessage,
    SenderRejected,
    SenderUnavailable,
)


class SmtpSender:
    name = "smtp"
    channels = frozenset({Channel.EMAIL})

    def __init__(self, host: str, port: int, sender: str, *, timeout_seconds: float = 5.0) -> None:
        self._host, self._port, self._from, self._timeout = host, port, sender, timeout_seconds

    async def send(self, message: OutboundMessage) -> None:
        mail = EmailMessage()
        mail["From"], mail["To"], mail["Subject"] = (
            self._from,
            message.recipient,
            message.subject or "",
        )
        mail.set_content(message.body)
        await asyncio.to_thread(self._send_blocking, mail)

    def _send_blocking(self, mail: EmailMessage) -> None:
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                smtp.send_message(mail)
        except smtplib.SMTPRecipientsRefused as exc:
            raise SenderRejected("recipient refused by the SMTP server") from exc
        except smtplib.SMTPResponseException as exc:
            # 5xx = permanent ("no such mailbox"), 4xx = try later / elsewhere
            if 500 <= exc.smtp_code < 600:
                raise SenderRejected(f"SMTP {exc.smtp_code}") from exc
            raise SenderUnavailable(f"SMTP {exc.smtp_code}") from exc
        except (
            OSError,
            smtplib.SMTPException,
        ) as exc:  # refused connection, DNS failure, timeout, dropped link
            raise SenderUnavailable(type(exc).__name__) from exc
