from pathlib import Path

import pytest
import sync_observability as so
import yaml

SLO = """
service: demo
slos:
  - {name: availability, objective: 99.9, window: 30d}
  - {name: latency, objective: 99.0, window: 30d, threshold_seconds: 0.5}
"""
RUNBOOK = "# runbook\n\n## demo-availability-burn\nx\n\n## demo-latency-burn\ny\n"


def make_service(tmp_path: Path, slo: str = SLO, runbook: str = RUNBOOK) -> Path:
    obs = tmp_path / "services" / "demo" / "observability"
    obs.mkdir(parents=True)
    (obs / "slo.yaml").write_text(slo)
    (obs / "runbook.md").write_text(runbook)
    return obs


def test_latency_buckets_match_the_library() -> None:
    from platform_observability.metrics import LATENCY_BUCKETS_S

    assert so.LATENCY_BUCKETS_S == LATENCY_BUCKETS_S


def test_generates_three_burn_alerts_per_slo(tmp_path: Path) -> None:
    obs = make_service(tmp_path)
    out = tmp_path / "out"
    produced = so.process_service(obs, out)
    assert "demo.slo.rules.yml" in produced
    doc = yaml.safe_load((out / "rules" / "demo.slo.rules.yml").read_text())
    rules = doc["groups"][0]["rules"]
    assert len(rules) == 6  # 2 SLOs x 3 burn policies
    page = [r for r in rules if r["labels"]["severity"] == "page"]
    assert len(page) == 4
    first = rules[0]
    assert 'app_service="demo"' in first["expr"]
    assert "0.0144" in first["expr"]  # 14.4 x (1 - 0.999)
    assert first["annotations"]["runbook_url"].endswith("#demo-availability-burn")
    latency = next(r for r in rules if r["labels"]["slo"] == "latency")
    assert 'le="0.5"' in latency["expr"]


def test_missing_runbook_section_fails(tmp_path: Path) -> None:
    obs = make_service(tmp_path, runbook="# runbook\n\n## demo-availability-burn\nonly one\n")
    with pytest.raises(so.ObservabilityError, match="demo-latency-burn"):
        so.process_service(obs, None)


def test_latency_threshold_must_be_a_bucket_bound(tmp_path: Path) -> None:
    obs = make_service(
        tmp_path,
        slo="service: demo\nslos:\n  - {name: latency, objective: 99, threshold_seconds: 0.3}\n",
    )
    with pytest.raises(so.ObservabilityError, match="bucket"):
        so.process_service(obs, None)


def test_integer_bucket_bounds_render_like_prometheus() -> None:
    assert so._le(1.0) == "1"
    assert so._le(0.25) == "0.25"
    assert so._le(10.0) == "10"


def test_counter_ratio_slo_builds_a_bad_over_total_query(tmp_path: Path) -> None:
    slo = """
service: demo
slos:
  - {name: delivery, kind: counter_ratio, metric: demo_delivery_total, bad: {outcome: failed}, objective: 99.5}
"""
    runbook = "## demo-delivery-burn\nx\n"
    obs = make_service(tmp_path, slo=slo, runbook=runbook)
    out = tmp_path / "out"
    so.process_service(obs, out)
    rules = yaml.safe_load((out / "rules" / "demo.slo.rules.yml").read_text())["groups"][0]["rules"]
    assert len(rules) == 3
    expr = rules[0]["expr"]
    assert 'demo_delivery_total{app_service="demo",outcome=~"failed"}' in expr
    assert "0.072" in expr  # 14.4 x (1 - 0.995)


def test_counter_ratio_requires_the_prometheus_total_suffix(tmp_path: Path) -> None:
    """Regression (found in the live Notifications run): `notifications_delivery` matched no series; the counter is `..._total`."""
    slo = "service: demo\nslos:\n  - {name: d, kind: counter_ratio, metric: demo_delivery, bad: {outcome: failed}, objective: 99}\n"
    obs = make_service(tmp_path, slo=slo, runbook="## demo-d-burn\nx\n")
    with pytest.raises(so.ObservabilityError, match="_total"):
        so.process_service(obs, None)


@pytest.mark.parametrize(
    "bad_slo",
    [
        "{name: d, kind: counter_ratio, metric: 'x; drop', bad: {outcome: failed}, objective: 99}",
        "{name: d, kind: counter_ratio, metric: x_total, bad: {}, objective: 99}",
        '{name: d, kind: counter_ratio, metric: x_total, bad: {outcome: "a\\"b"}, objective: 99}',
    ],
)
def test_counter_ratio_rejects_unsafe_input(tmp_path: Path, bad_slo: str) -> None:
    obs = make_service(
        tmp_path, slo=f"service: demo\nslos:\n  - {bad_slo}\n", runbook="## demo-d-burn\nx\n"
    )
    with pytest.raises(so.ObservabilityError):
        so.process_service(obs, None)
