#!/usr/bin/env python3
"""Assemble per-service observability assets into deploy/observability/generated/ (git-ignored).

For every services/<name>/observability/:
  slo.yaml            -> generated/rules/<name>.slo.rules.yml   (multi-window, multi-burn-rate alerts, rule O-9)
  alerts.rules.yaml   -> generated/rules/<name>.rules.yml       (hand-written cause alerts, if any)
  dashboards/*.json   -> generated/dashboards/<name>/*.json
and FAILS if an alert's runbook anchor is missing from runbook.md (rule O-8).

    uv run python tools/sync_observability.py            # regenerate
    uv run python tools/sync_observability.py --lint     # validate only, write nothing

Metric names below assume OTLP -> Prometheus conversion: `http.server.request.duration` (unit s) becomes
`http_server_request_duration_seconds_{bucket,count,sum}`, and attributes become labels (`app.service` -> `app_service`).
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
GENERATED = ROOT / "deploy" / "observability" / "generated"

# Must equal platform_observability.metrics.LATENCY_BUCKETS_S (asserted in tools/tests).
LATENCY_BUCKETS_S: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

# (burn rate, long window, short window, severity, for)  - Google SRE Workbook, "Alerting on SLOs"
BURN_POLICIES: tuple[tuple[float, str, str, str, str], ...] = (
    (14.4, "1h", "5m", "page", "2m"),
    (6.0, "6h", "30m", "page", "15m"),
    (1.0, "3d", "6h", "ticket", "1h"),
)

METRIC = "http_server_request_duration_seconds"


class ObservabilityError(Exception):
    pass


def _le(value: float) -> str:
    """Prometheus renders bucket bounds without a trailing .0 (1.0 -> "1")."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _selector(service: str, extra: str = "") -> str:
    base = f'app_service="{service}",http_route=~"/api/.*"'
    return base + (f",{extra}" if extra else "")


_METRIC_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_VALUE_RE = re.compile(r"^[\w.|*+\-]+$")


def _counter_ratio(service: str, slo: dict[str, Any], window: str) -> str:
    """Bad/total ratio of any counter, e.g. notifications_delivery_total{outcome="failed"} / all of it."""
    metric = str(slo.get("metric", ""))
    if not _METRIC_RE.match(metric):
        raise ObservabilityError(
            f"{service}: counter_ratio SLO needs a valid 'metric' name, got {metric!r}"
        )
    if not metric.endswith("_total"):
        # The OTel -> Prometheus exporter appends _total to counters; without it the query silently matches nothing.
        raise ObservabilityError(
            f"{service}: counter_ratio metric must be the Prometheus counter name ending in _total, got {metric!r}"
        )
    bad = slo.get("bad", {})
    if not bad:
        raise ObservabilityError(
            f"{service}: counter_ratio SLO needs a non-empty 'bad' label filter"
        )
    base = f'app_service="{service}"'
    selectors = [base]
    for label, value in bad.items():
        if not _LABEL_RE.match(str(label)) or not _VALUE_RE.match(str(value)):
            raise ObservabilityError(
                f"{service}: unsafe label filter {label}={value!r} in counter_ratio SLO"
            )
        selectors.append(f'{label}=~"{value}"')
    total = f"sum(rate({metric}{{{base}}}[{window}]))"
    errors = f"sum(rate({metric}{{{','.join(selectors)}}}[{window}]))"
    return f"({errors} / {total})"


def bad_ratio(service: str, slo: dict[str, Any], window: str) -> str:
    kind = slo.get("kind", slo["name"])  # `kind` defaults to the SLO name (availability | latency)
    if kind == "counter_ratio":
        return _counter_ratio(service, slo, window)
    total = f"sum(rate({METRIC}_count{{{_selector(service)}}}[{window}]))"
    if kind == "availability":
        five_xx = 'http_response_status_code=~"5.."'
        errors = f"sum(rate({METRIC}_count{{{_selector(service, five_xx)}}}[{window}]))"
        return f"({errors} / {total})"
    if kind == "latency":
        threshold = float(slo["threshold_seconds"])
        if threshold not in LATENCY_BUCKETS_S:
            raise ObservabilityError(
                f"{service}: latency threshold {threshold}s must be one of the histogram bucket bounds {LATENCY_BUCKETS_S}"
            )
        le_filter = f'le="{_le(threshold)}"'
        fast = f"sum(rate({METRIC}_bucket{{{_selector(service, le_filter)}}}[{window}]))"
        return f"(1 - {fast} / {total})"
    raise ObservabilityError(
        f"{service}: unknown SLO kind {kind!r} (expected availability | latency | counter_ratio)"
    )


def anchor(service: str, slo_name: str) -> str:
    return f"{service}-{slo_name}-burn"


def slo_rules(service: str, slo_doc: dict[str, Any]) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    for slo in slo_doc.get("slos", []):
        budget = (100.0 - float(slo["objective"])) / 100.0
        pretty = f"{service.capitalize()}{slo['name'].capitalize()}BudgetBurn"
        for burn, long_w, short_w, severity, for_ in BURN_POLICIES:
            limit = f"{burn * budget:.6g}"
            expr = (
                f"({bad_ratio(service, slo, long_w)} > {limit})\n"
                f"and\n({bad_ratio(service, slo, short_w)} > {limit})"
            )
            rules.append(
                {
                    "alert": pretty,
                    "expr": expr,
                    "for": for_,
                    "labels": {
                        "severity": severity,
                        "app_service": service,
                        "slo": slo["name"],
                        "burn_rate": str(burn),
                    },
                    "annotations": {
                        "summary": f"{service} {slo['name']} SLO is burning {burn}x faster than allowed ({long_w}/{short_w})",
                        "description": (
                            f"Objective {slo['objective']}% over {slo.get('window', '30d')}. "
                            f"{slo.get('description', '')}".strip()
                        ),
                        "runbook_url": f"services/{service}/observability/runbook.md#{anchor(service, slo['name'])}",
                        "dashboard_url": f"/d/red-overview?var-app_service={service}",
                    },
                }
            )
    return {"groups": [{"name": f"{service}-slo", "rules": rules}]}


def runbook_anchors(runbook: Path) -> set[str]:
    if not runbook.exists():
        return set()
    return {line[3:].strip() for line in runbook.read_text().splitlines() if line.startswith("## ")}


def check_runbook(service: str, rule_docs: list[dict[str, Any]], runbook: Path) -> None:
    anchors = runbook_anchors(runbook)
    for doc in rule_docs:
        for group in doc.get("groups", []):
            for rule in group.get("rules", []):
                if "alert" not in rule:
                    continue
                ann = rule.get("annotations", {})
                if (
                    "summary" not in ann
                    or "runbook_url" not in ann
                    or "severity" not in rule.get("labels", {})
                ):
                    raise ObservabilityError(
                        f"{service}: alert {rule['alert']} needs labels.severity and annotations.summary/runbook_url (rule O-8)"
                    )
                wanted = ann["runbook_url"].split("#", 1)[-1]
                if wanted not in anchors:
                    raise ObservabilityError(
                        f"{service}: runbook.md has no section '## {wanted}' for alert {rule['alert']} (rule O-8)"
                    )


def process_service(service_dir: Path, out_dir: Path | None) -> list[str]:
    service = service_dir.parent.name
    obs = service_dir
    produced: list[str] = []
    rule_docs: list[dict[str, Any]] = []

    slo_file = obs / "slo.yaml"
    if slo_file.exists():
        doc = yaml.safe_load(slo_file.read_text()) or {}
        if doc.get("service", service) != service:
            raise ObservabilityError(f"{slo_file}: 'service' must be '{service}'")
        generated = slo_rules(service, doc)
        rule_docs.append(generated)
        if out_dir:
            (out_dir / "rules").mkdir(parents=True, exist_ok=True)
            (out_dir / "rules" / f"{service}.slo.rules.yml").write_text(
                f"# GENERATED from services/{service}/observability/slo.yaml - do not edit\n"
                + yaml.safe_dump(generated, sort_keys=False, width=200)
            )
        produced.append(f"{service}.slo.rules.yml")

    alerts_file = obs / "alerts.rules.yaml"
    if alerts_file.exists():
        doc = yaml.safe_load(alerts_file.read_text()) or {}
        if doc.get("groups"):
            rule_docs.append(doc)
            if out_dir:
                (out_dir / "rules").mkdir(parents=True, exist_ok=True)
                (out_dir / "rules" / f"{service}.rules.yml").write_text(alerts_file.read_text())
            produced.append(f"{service}.rules.yml")

    check_runbook(service, rule_docs, obs / "runbook.md")

    dashboards = (
        sorted((obs / "dashboards").glob("*.json")) if (obs / "dashboards").exists() else []
    )
    if out_dir and dashboards:
        target = out_dir / "dashboards" / service
        target.mkdir(parents=True, exist_ok=True)
        for d in dashboards:
            shutil.copy2(d, target / d.name)
    produced += [f"dashboards/{service}/{d.name}" for d in dashboards]
    return produced


def reset_generated(out: Path) -> None:
    """Empty the generated folders but keep them (and a .gitkeep): docker-compose bind-mounts them, and a
    missing host folder would be created root-owned by Docker."""
    for sub in ("rules", "dashboards"):
        folder = out / sub
        folder.mkdir(parents=True, exist_ok=True)
        for child in folder.iterdir():
            if child.name == ".gitkeep":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        (folder / ".gitkeep").touch()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--lint", action="store_true", help="validate only; write nothing")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root: Path = args.root
    out = root / "deploy" / "observability" / "generated"

    if not args.lint:
        reset_generated(out)

    produced: list[str] = []
    try:
        for obs in sorted((root / "services").glob("*/observability")):
            produced += process_service(obs, None if args.lint else out)
    except ObservabilityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"{'Validated' if args.lint else 'Generated'} {len(produced)} observability asset(s)")
    for name in produced:
        print("  ", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
