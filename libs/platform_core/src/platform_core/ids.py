"""Time-ordered identifiers (rule D-9). UUIDv7 per RFC 9562 (not in the 3.12 stdlib)."""

import secrets
import time
from uuid import UUID

_RAND_BITS = 74


def uuid7() -> UUID:
    unix_ms = time.time_ns() // 1_000_000
    rand = secrets.randbits(_RAND_BITS)
    rand_a = rand >> 62  # 12 bits
    rand_b = rand & ((1 << 62) - 1)  # 62 bits
    value = (
        ((unix_ms & ((1 << 48) - 1)) << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    )
    return UUID(int=value)
