"""Recipient rules: normalise, validate, mask, fingerprint. Pure functions (rule L-2)."""

import hashlib
import hmac
import re

from notifications_contracts import Channel
from notifications_service.domain.errors import InvalidRecipient

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_NOISE = re.compile(r"[\s\-().]")


def normalise_recipient(channel: Channel, raw: str) -> str:
    """Canonical form, so the same person can't dodge the rate limit with `A@x.com` vs `a@x.com`."""
    value = raw.strip()
    if channel is Channel.SMS:
        value = _PHONE_NOISE.sub("", value)
        if not _E164.match(value):
            raise InvalidRecipient(
                details={"channel": channel.value, "hint": "use E.164, e.g. +14155550123"}
            )
        return value
    value = value.lower()
    if len(value) > 254 or not _EMAIL.match(value):
        raise InvalidRecipient(details={"channel": channel.value})
    return value


def mask_recipient(channel: Channel, recipient: str) -> str:
    """What we are willing to store and log: enough for support to recognise, not enough to contact."""
    if channel is Channel.SMS:
        return f"{recipient[:3]}{'*' * max(len(recipient) - 5, 1)}{recipient[-2:]}"
    local, _, domain = recipient.partition("@")
    return f"{local[:1]}***@{domain}"


def recipient_digest(pepper: bytes, channel: Channel, recipient: str) -> str:
    """Keyed hash (HMAC-SHA256): lets us count messages per recipient without storing the recipient."""
    return hmac.new(pepper, f"{channel.value}:{recipient}".encode(), hashlib.sha256).hexdigest()
