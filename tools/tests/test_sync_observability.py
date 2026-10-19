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
