"""Business metrics declared once (rule O-5). Attributes are closed sets — never IDs, recipients or free text."""

from collections.abc import Mapping, Sequence

from notifications_service.domain.providers import PROVIDER_NAMES
from platform_observability import Counter, Histogram, app_service_scope

_CHANNELS = frozenset({"sms", "email"})

# One increment per delivery, by final outcome. `failed` (every provider unavailable) is what the SLO counts as bad;
# `rejected` (the recipient itself is bad) is the caller's problem, not ours.
DELIVERIES = Counter(
    "notifications.delivery",
    allowed={"channel": _CHANNELS, "outcome": frozenset({"sent", "rejected", "failed"})},
    description="Final outcome of each delivery",
    scope="notifications_service",
)

# One increment per provider call: shows failover happening (a spike of unavailable on 'smtp' + sent on 'console').
PROVIDER_ATTEMPTS = Counter(
    "notifications.provider.attempt",
    allowed={
        "channel": _CHANNELS,
        "provider": PROVIDER_NAMES,
        "outcome": frozenset({"sent", "rejected", "unavailable", "timeout"}),
    },
    description="Outcome of each provider call",
    scope="notifications_service",
)

PROVIDER_DURATION = Histogram(
    "notifications.provider.duration",
    allowed={"channel": _CHANNELS, "provider": PROVIDER_NAMES},
    description="Time spent in one provider call",
    unit="s",
    scope="notifications_service",
)

RATE_LIMITED = Counter(
    "notifications.rate_limited",
    allowed={"channel": _CHANNELS},
    description="Sends refused by the per-recipient hourly cap (SMS-pumping defence)",
    scope="notifications_service",
)


_DELIVERY_OUTCOMES = ("sent", "rejected", "failed")
_ATTEMPT_OUTCOMES = ("sent", "rejected", "unavailable", "timeout")


def prime_metrics(chains: Mapping[str, Sequence[str]]) -> None:
    """Create every series at 0 when the service starts.

    Prometheus computes rate()/increase() from the *change* between samples. A counter series that first appears
    already at 1 (the first failure ever) or 3 (three failures in the first scrape interval) has no earlier sample,
    so that jump is invisible and the SLO under-counts exactly the failures that matter. Because our label values are
    closed sets we know every series up front, so we publish them all at zero (found in the live run, see A-B 03).
    `chains` maps channel -> provider names that are actually configured.
    """
    with app_service_scope("notifications"):
        for channel in _CHANNELS:
            for outcome in _DELIVERY_OUTCOMES:
                DELIVERIES.add(0, channel=channel, outcome=outcome)
            RATE_LIMITED.add(0, channel=channel)
        for channel, providers in chains.items():
            for provider in providers:
                for outcome in _ATTEMPT_OUTCOMES:
                    PROVIDER_ATTEMPTS.add(0, channel=channel, provider=provider, outcome=outcome)
