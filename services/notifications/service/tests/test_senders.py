import smtplib
from email.message import EmailMessage
from typing import Any, ClassVar

import pytest

from notifications_contracts import Channel
from notifications_service.application.ports import (
    OutboundMessage,
    SenderRejected,
    SenderUnavailable,
)
from notifications_service.infrastructure.providers.console import ConsoleSender
from notifications_service.infrastructure.providers.memory import InMemorySender
from notifications_service.infrastructure.providers.smtp import SmtpSender
from notifications_service.infrastructure.providers.static import StaticSender

EMAIL = OutboundMessage(Channel.EMAIL, "asha@example.com", "Hello", "body text")


async def test_memory_sender_remembers_and_clears() -> None:
    sender = InMemorySender()
    await sender.send(EMAIL)
    assert sender.messages() == [EMAIL]
    sender.clear()
    assert sender.sent == []


async def test_static_sender_answers_as_configured() -> None:
    await StaticSender("accept").send(EMAIL)
    with pytest.raises(SenderRejected):
        await StaticSender("reject").send(EMAIL)
    with pytest.raises(SenderUnavailable):
        await StaticSender("unavailable").send(EMAIL)


async def test_console_sender_logs_the_message(capsys: pytest.CaptureFixture[str]) -> None:
    await ConsoleSender().send(EMAIL)  # must not raise; visibility is covered by the live run


class FakeSmtp:
    """Stands in for smtplib.SMTP and fails in a chosen way."""

    failure: ClassVar[BaseException | None] = None
    delivered: ClassVar[list[EmailMessage]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def send_message(self, mail: EmailMessage) -> None:
        if self.failure:
            raise self.failure
        self.delivered.append(mail)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSmtp]:
    FakeSmtp.failure, FakeSmtp.delivered = None, []
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    return FakeSmtp


async def test_smtp_sender_builds_a_proper_email(fake_smtp: type[FakeSmtp]) -> None:
    await SmtpSender("mailpit", 1025, "no-reply@x.test").send(EMAIL)
    mail = fake_smtp.delivered[0]
    assert (mail["To"], mail["From"], mail["Subject"]) == (
        "asha@example.com",
        "no-reply@x.test",
        "Hello",
    )
    assert mail.get_content().strip() == "body text"


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (smtplib.SMTPRecipientsRefused({"a": (550, b"no")}), SenderRejected),
        (smtplib.SMTPResponseException(553, b"mailbox name invalid"), SenderRejected),
        (smtplib.SMTPResponseException(451, b"try later"), SenderUnavailable),
        (smtplib.SMTPServerDisconnected("gone"), SenderUnavailable),
        (ConnectionRefusedError(), SenderUnavailable),
        (TimeoutError(), SenderUnavailable),
    ],
)
async def test_smtp_errors_map_to_reject_or_unavailable(
    fake_smtp: type[FakeSmtp], failure: BaseException, expected: type[Exception]
) -> None:
    fake_smtp.failure = failure
    with pytest.raises(expected):
        await SmtpSender("mailpit", 1025, "no-reply@x.test").send(EMAIL)


async def test_smtp_to_a_closed_port_is_unavailable_not_a_crash() -> None:
    with pytest.raises(SenderUnavailable):
        await SmtpSender("127.0.0.1", 1, "a@b.test", timeout_seconds=1).send(EMAIL)


def test_channels_are_declared() -> None:
    assert SmtpSender("h", 1, "a@b.c").channels == {Channel.EMAIL}
    assert ConsoleSender().channels == set(Channel)
    _: Any = None
