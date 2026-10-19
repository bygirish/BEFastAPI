#!/usr/bin/env python3
"""End-to-end proof that the observability stack works and the signals are CORRELATED.

Sends one request to a service, then verifies (polling, since pipelines are asynchronous):
  1. /readyz is OK
  2. the JSON log line for that request reached Loki and carries a trace_id
  3. that exact trace is in Tempo and contains the use-case span
  4. the request-duration metric (with app_service) is in Prometheus
  5. Grafana is healthy with the 4 provisioned datasources and the base dashboards
  6. Alertmanager is ready and Prometheus loaded this service's SLO rules (when slo.yaml exists)

    uv run python tools/obs_smoke.py --service demo
"""

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any

Check = Callable[[], str]


def http_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, headers=headers or {})  # noqa: S310 - local URLs only
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        body = resp.read().decode()
        return json.loads(body) if body.strip().startswith(("{", "[")) else body


def poll(check: Check, timeout: float, interval: float = 2.0) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout
    last = "no attempt"
    while time.monotonic() < deadline:
        try:
            return True, check()
        except Exception as exc:  # noqa: BLE001 - keep polling, report the last reason
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(interval)
    return False, last


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--service", required=True, help="logical service to call (uses /api/v1/<service>/ping)"
    )
    ap.add_argument("--app", default="http://localhost:8000")
    ap.add_argument("--tempo", default="http://localhost:3200")
    ap.add_argument("--loki", default="http://localhost:3100")
    ap.add_argument("--prometheus", default="http://localhost:9090")
    ap.add_argument("--grafana", default="http://localhost:3000")
    ap.add_argument("--alertmanager", default="http://localhost:9093")
    ap.add_argument("--grafana-auth", default="admin:admin")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    svc = args.service
    request_id = f"smoke-{uuid.uuid4().hex[:12]}"
    results: list[tuple[str, bool, str]] = []
    state: dict[str, str] = {}

    def record(name: str, ok: bool, detail: str) -> bool:
        results.append((name, ok, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<46} {detail}")
        return ok

    print(f"obs-smoke for service '{svc}' (request id {request_id})")

    ok, detail = poll(lambda: str(http_json(f"{args.app}/readyz")["status"]), 60)
    record("app /readyz is ok", ok and detail == "ok", detail)

    def call_service() -> str:
        url = f"{args.app}/api/v1/{svc}/ping"
        req = urllib.request.Request(url, headers={"X-Request-ID": request_id})  # noqa: S310
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            echoed = resp.headers.get("x-request-id") == request_id
            return f"HTTP {resp.status}, x-request-id echoed={echoed}"

    ok, detail = poll(call_service, 30)
    record(f"GET /api/v1/{svc}/ping", ok, detail)

    def find_log() -> str:
        now = time.time_ns()
        query = urllib.parse.urlencode(
            {
                "query": f'{{service_name=~".+"}} |= "{request_id}" |= "http_request_completed"',
                "start": now - 600 * 10**9,
                "end": now + 60 * 10**9,
                "limit": 5,
            }
        )
        data = http_json(f"{args.loki}/loki/api/v1/query_range?{query}")
        streams = data["data"]["result"]
        if not streams:
            raise LookupError("no log line yet")
        line = json.loads(streams[0]["values"][0][1])
        state["trace_id"] = line["trace_id"]
        assert line.get("app.service") == svc, f"app.service={line.get('app.service')!r}"
        return f"trace_id={line['trace_id'][:12]}…, app.service={line['app.service']}, request_id matches"

    ok, detail = poll(find_log, args.timeout)
    record("Loki: JSON log has trace_id + app.service", ok, detail)

    def find_trace() -> str:
        data = http_json(f"{args.tempo}/api/traces/{state['trace_id']}")
        names = {
            s["name"]
            for rs in data.get("batches", [])
            for ss in rs.get("scopeSpans", [])
            for s in ss.get("spans", [])
        }
        if f"{svc}.Ping" not in names:
            raise LookupError(f"use-case span {svc}.Ping not in {sorted(names)}")
        return f"{len(names)} span name(s), includes {svc}.Ping"

    if "trace_id" in state:
        ok, detail = poll(find_trace, args.timeout)
        record("Tempo: the SAME trace_id has the use-case span", ok, detail)
    else:
        record(
            "Tempo: the SAME trace_id has the use-case span",
            False,
            "skipped: no trace_id from the log",
        )

    def find_metric() -> str:
        q = urllib.parse.quote(
            f'sum(http_server_request_duration_seconds_count{{app_service="{svc}"}})'
        )
        data = http_json(f"{args.prometheus}/api/v1/query?query={q}")
        result = data["data"]["result"]
        if not result or float(result[0]["value"][1]) < 1:
            raise LookupError("metric not there yet")
        return f"count={result[0]['value'][1]} (labelled app_service={svc})"

    ok, detail = poll(find_metric, args.timeout)
    record("Prometheus: request metric with app_service", ok, detail)

    auth = {"Authorization": "Basic " + base64.b64encode(args.grafana_auth.encode()).decode()}

    def grafana_ok() -> str:
        health = http_json(f"{args.grafana}/api/health")
        sources = {d["uid"] for d in http_json(f"{args.grafana}/api/datasources", headers=auth)}
        missing = {"prometheus", "tempo", "loki", "alertmanager"} - sources
        if missing:
            raise LookupError(f"missing datasources {sorted(missing)}")
        titles = {
            d["title"] for d in http_json(f"{args.grafana}/api/search?type=dash-db", headers=auth)
        }
        need = {
            "RED overview (per logical service)",
            "Platform health (postgres, redis, collector)",
        }
        if not need <= titles:
            raise LookupError(f"missing dashboards {sorted(need - titles)}")
        return f"db={health.get('database')}, 4 datasources, {len(titles)} dashboards"

    ok, detail = poll(grafana_ok, 90)
    record("Grafana: healthy, datasources + dashboards", ok, detail)

    def rules_loaded() -> str:
        http_json(f"{args.alertmanager}/-/ready")
        groups = http_json(f"{args.prometheus}/api/v1/rules")["data"]["groups"]
        names = {g["name"] for g in groups}
        if f"{svc}-slo" not in names:
            raise LookupError(f"group {svc}-slo not loaded; have {sorted(names)}")
        return f"alertmanager ready; Prometheus loaded group {svc}-slo"

    ok, detail = poll(rules_loaded, 60)
    record("Alertmanager ready + SLO rules loaded", ok, detail)

    failed = [n for n, ok_, _ in results if not ok_]
    print(f"\n{'ALL CHECKS PASSED' if not failed else 'FAILED: ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
