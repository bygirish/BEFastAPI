#!/usr/bin/env python3
"""Background traffic for the live demo: mostly healthy requests, a few slow ones, a few bugs.

It exists so the dashboards, traces, logs and alerts have something real to show during a demo.

    uv run python tools/demo_traffic.py --base http://localhost:18000 --service demo
"""

import argparse
import random
import signal
import sys
import time
import urllib.error
import urllib.request
from types import FrameType


def hit(base: str, path: str, request_id: str) -> int:
    request = urllib.request.Request(base + path, headers={"X-Request-ID": request_id})  # noqa: S310 - local demo URL
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except OSError:
        return 0  # app not reachable (restarting?) - keep going


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="http://localhost:18000")
    parser.add_argument("--service", default="demo")
    parser.add_argument("--rate", type=float, default=3.0, help="requests per second")
    parser.add_argument(
        "--slow-pct",
        type=float,
        default=10.0,
        help="percent of requests that are slow (300-900 ms)",
    )
    parser.add_argument(
        "--fail-pct",
        type=float,
        default=4.0,
        help="percent of requests that hit a simulated bug (HTTP 500)",
    )
    args = parser.parse_args()

    running = True

    def stop(signum: int, frame: FrameType | None) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    rng = random.Random(7)  # noqa: S311 - not security related
    prefix = f"/api/v1/{args.service}"
    counts: dict[int, int] = {}
    sent = 0
    last_report = time.monotonic()
    while running:
        roll = rng.random() * 100
        if roll < args.fail_pct:
            path = f"{prefix}/fail"
        elif roll < args.fail_pct + args.slow_pct:
            path = f"{prefix}/slow?ms={rng.randint(300, 900)}"
        elif roll < args.fail_pct + args.slow_pct + 3:
            path = f"{prefix}/slow?ms=not-a-number"  # a 422 caller mistake
        elif roll < args.fail_pct + args.slow_pct + 6:
            path = f"{prefix}/does-not-exist"  # a 404
        else:
            path = f"{prefix}/ping"
        sent += 1
        status = hit(args.base, path, f"demo-{sent:06d}")
        counts[status] = counts.get(status, 0) + 1
        if time.monotonic() - last_report >= 10:
            print(f"sent={sent} statuses={dict(sorted(counts.items()))}", flush=True)
            last_report = time.monotonic()
        time.sleep(max(0.0, rng.expovariate(args.rate)))
    print(f"stopped after {sent} requests: {dict(sorted(counts.items()))}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
