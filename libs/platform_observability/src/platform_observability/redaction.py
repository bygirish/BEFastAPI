"""Secret/PII redaction shared by logs and span attributes (rule O-4, test T-8)."""

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

# Key fragments (case-insensitive) whose values are never emitted.
DENY_KEY_FRAGMENTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "otp",
    "pin",
    "private_key",
    "credential",
    "set-cookie",
)
# `code` is only sensitive when it is a verification/OTP code.
DENY_EXACT_KEYS: frozenset[str] = frozenset({"code", "verification_code", "otp_code"})

_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*\b")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in DENY_EXACT_KEYS:
        return True
    return any(fragment in lowered for fragment in DENY_KEY_FRAGMENTS)


def redact_string(value: str) -> str:
    value = _JWT_RE.sub(REDACTED, value)
    value = _BEARER_RE.sub(f"Bearer {REDACTED}", value)
    return _CARD_RE.sub(REDACTED, value)


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Recursively redact mappings/sequences/strings. Depth-limited to stay cheap."""
    if _depth > 6:
        return value
    if isinstance(value, Mapping):
        return {
            k: (
                REDACTED
                if isinstance(k, str) and is_sensitive_key(k)
                else redact(v, _depth=_depth + 1)
            )
            for k, v in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return (
            type(value)(redact(v, _depth=_depth + 1) for v in value)
            if not isinstance(value, set | frozenset)
            else [redact(v, _depth=_depth + 1) for v in value]
        )
    if isinstance(value, str):
        return redact_string(value)
    return value


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return REDACTED
    return f"{local[:1]}***@{domain}"


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return REDACTED
    prefix = "+" if phone.strip().startswith("+") else ""
    return f"{prefix}{'*' * (len(digits) - 4)}{digits[-4:]}"
