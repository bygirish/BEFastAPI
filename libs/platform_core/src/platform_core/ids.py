"""Time-ordered identifiers (rule D-9). UUIDv7 per RFC 9562 (not in the 3.12 stdlib).

Layout (128 bits):  48-bit unix-ms | 4-bit version (7) | 12-bit counter | 2-bit variant | 62 random bits

IDs from the same process are strictly increasing, even inside one millisecond: the 12-bit field after the
version is used as a counter (RFC 9562 §6.2, "Method 1"), re-seeded randomly whenever the millisecond changes.
Across processes ordering is only guaranteed to the millisecond, which is all that sorting by id needs.
"""

import secrets
import threading
import time
from uuid import UUID

_lock = threading.Lock()
_last_ms = -1
_counter = 0
_COUNTER_MAX = (1 << 12) - 1
_COUNTER_SEED_MAX = 1 << 11  # start in the lower half so a burst has headroom before overflow


def uuid7() -> UUID:
    global _last_ms, _counter
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms:
            _last_ms = now_ms
            _counter = secrets.randbelow(_COUNTER_SEED_MAX)
        else:
            _counter += 1
            if _counter > _COUNTER_MAX:  # >4000 ids in one ms: borrow from the next millisecond
                _last_ms += 1
                _counter = secrets.randbelow(_COUNTER_SEED_MAX)
        unix_ms, counter = _last_ms, _counter

    rand_b = secrets.randbits(62)
    value = (
        ((unix_ms & ((1 << 48) - 1)) << 80) | (0x7 << 76) | (counter << 64) | (0b10 << 62) | rand_b
    )
    return UUID(int=value)
