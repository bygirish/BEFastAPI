"""Turns provider NAMES from configuration into adapter objects, and chains them per channel."""

from collections.abc import Callable, Mapping

from notifications_contracts import Channel
from notifications_service.application.ports import Sender
from notifications_service.domain.providers import PROVIDER_NAMES
from notifications_service.infrastructure.providers.console import ConsoleSender
from notifications_service.infrastructure.providers.memory import InMemorySender
from notifications_service.infrastructure.providers.smtp import SmtpSender
from notifications_service.infrastructure.providers.static import StaticSender
from notifications_service.settings import NotificationsSettings

_FACTORIES: dict[str, Callable[[NotificationsSettings], Sender]] = {
    "console": lambda s: ConsoleSender(),
    "memory": lambda s: InMemorySender(),
    "static": lambda s: StaticSender(s.static_outcome),
    "smtp": lambda s: SmtpSender(
        s.smtp_host, s.smtp_port, s.smtp_from, timeout_seconds=s.attempt_timeout_seconds
    ),
}
assert _FACTORIES.keys() == PROVIDER_NAMES, (
    "domain.providers.PROVIDER_NAMES and the registry drifted apart"
)


def build_senders(settings: NotificationsSettings) -> dict[str, Sender]:
    """One instance per provider name that is actually used (so unused vendors cost nothing)."""
    wanted = [*settings.sms_providers, *settings.email_providers]
    return {name: _FACTORIES[name](settings) for name in dict.fromkeys(wanted)}


def build_chains(
    settings: NotificationsSettings, senders: Mapping[str, Sender]
) -> dict[Channel, list[Sender]]:
    chains: dict[Channel, list[Sender]] = {}
    for channel, names in (
        (Channel.SMS, settings.sms_providers),
        (Channel.EMAIL, settings.email_providers),
    ):
        chain = [senders[name] for name in names]
        unsupported = [s.name for s in chain if channel not in s.channels]
        if unsupported:
            raise ValueError(f"provider(s) {unsupported} cannot deliver {channel.value}")
        chains[channel] = chain
    return chains
