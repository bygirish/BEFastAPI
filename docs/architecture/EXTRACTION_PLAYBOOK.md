# Extraction Playbook — from module to microservice

Status: **DRAFT for review** · Last updated: 2026-10-19

Target: a service that satisfies [STANDARDS.md](STANDARDS.md) can be extracted, deployed, and cut over in **≈ 1–2 engineer-days of
mechanical work** (plus soak time). If it takes longer, a rule was broken — fix the rule violation, then extract.

---

## 1. Don't extract by default

A modular monolith is a valid end state. Extraction costs: a new pipeline, on-call surface, network failure modes, versioned contracts,
distributed tracing, data-movement risk. Pay it only on evidence.

## 2. Triggers (need at least one, written in an ADR)

| Trigger | Evidence to attach |
|---|---|
| **Independent scaling** | Service is CPU/IO-heavy or spiky vs. the rest (e.g. Files: uploads/processing; Notifications: fan-out). Metrics show the monolith scales for one service's sake |
| **Fault isolation** | Incidents where one service's failure/latency degraded unrelated flows |
| **Release cadence / team ownership** | A separate team owns it and is blocked by the shared release train |
| **Security / compliance** | Needs separate network zone, data residency, audit scope (e.g. Auth with credentials/PII) |
| **Resource profile** | Needs different runtime (GPU, workers, memory) or different language/stack |
| **Cost** | Per-service cost attribution shows material waste from co-hosting |

Not triggers: "microservices are modern", a hunch about future load, a single slow query (fix the query).

## 3. Readiness scorecard (all must be ✅ before starting)

Run `tools/extraction_drill.py --service <name> --report`. It checks:

| # | Check | How verified |
|---|---|---|
| 1 | No imports of other services' internals | import-linter green |
| 2 | Service runs alone via `apps/<name>_api` with other ports bound to fakes | extraction drill |
| 3 | Own tables only, own schema, no cross-schema FK/join/view | `check_db_isolation.py` |
| 4 | Own Alembic env migrates an empty DB to head | drill |
| 5 | `<name>_contracts` covers 100 % of what other services use; contract tests pass for Impl **and** HttpClient | CI |
| 6 | All outbound events go through outbox; handlers idempotent | event lint + tests |
| 7 | No sync chain >1 hop involving this service | trace sample / review |
| 8 | Own settings with `<NAME>_` prefix; no foreign env reads | grep/lint |
| 9 | Dockerfile builds; image starts and `/readyz` passes | CI |
| 10 | Dependency list in its own `pyproject.toml` is complete (clean venv install works) | drill |
| 11 | `platform_*` libs consumed only as versioned packages (no path hacks) | CI |
| 12 | Redis/object-storage keys namespaced | key-naming lint |
| 13 | `observability/` assets present and lint-clean (SLOs, alert rules, dashboards, runbook); telemetry contract + redaction tests pass | rules/dashboard lint, T-8 |
| 14 | All signals carry `app.service`; dashboards filter by `app_service` (not `service.name`) | telemetry contract test, dashboard lint |

Anything ❌ is a **pre-extraction fix inside the monolith** (still deployable) — never fix it during cutover.

---

## 4. Step-by-step

> Each step leaves the system deployable and reversible. Steps 1–4 are non-production prep; the production risk is concentrated in steps 5–7.

### Step 1 — Freeze and snapshot (½ h)
- Tag the monolith (`pre-extract-<name>-YYYYMMDD`). Announce a contract freeze for `<name>_contracts` (additive-only already; now no changes).
- Record baseline: p50/p95/p99, error rate, throughput of the service's endpoints and its callers.

### Step 2 — Create the new repo with history (1 h)
```bash
git clone <monolith> <name>-service && cd <name>-service
git filter-repo --subdirectory-filter services/<name>        # or: git subtree split -P services/<name>
```
Resulting repo root contains `service/` (package, migrations, tests), `contracts/`, `observability/`, `Dockerfile`, `README.md`.
- Add a root `pyproject.toml` with a `[tool.uv.workspace]` (`members = ["service", "contracts"]`) — the same shape as the monorepo — plus the lint/type config copied from the monorepo root, and generate the repo's `.importlinter` from the same template (`tools/sync_workspace.py` logic, two roots).
- Replace workspace references to `libs/platform_*` with pinned versions (`platform-core==x.y.z` from the private index, or git tags).
- Publish `<name>-contracts` (independent version, semver) to the private index. Consumers will depend on it as a normal package.
- Copy the CI template (lint, mypy, import-linter for this repo's two roots, tests, container build, contract tests, `promtool`/dashboard lint).
- `services/<name>/observability/` (SLOs, alert rules, dashboards, runbook) comes along with the filter — register it with the shared Prometheus/Grafana provisioning of the target environment.

### Step 3 — Stand up infra for the service (2–4 h)
- New database (or schema on a new cluster) + role. Secrets in the secret manager. Redis namespace/instance. Broker topic/stream (if events leave the process).
- Point `OTEL_EXPORTER_OTLP_ENDPOINT` at the shared Collector; set `OTEL_SERVICE_NAME=<name>-service` (`app.service` stays `<name>`). Add the service to the compose `split` profile / Helm chart.
- IaC/Helm/compose for the service: env vars `<NAME>_*`, readiness `/readyz`, liveness `/healthz`, resources, autoscaling policy.

### Step 4 — Move the data (2–4 h, rehearse first)
1. Rehearse on staging: `pg_dump --schema=<name> -Fc | pg_restore` into the new DB; run the service's Alembic `current` (should equal head).
2. Production plan (choose by size/downtime tolerance):
   - **Small / maintenance window OK:** stop writes → dump/restore → verify row counts + checksums → switch URL.
   - **Large / zero-downtime:** logical replication from the shared cluster's `<name>` schema to the new DB; switch the URL at lag≈0 (writes are only by this service, so there is a single writer — easy cutover).
3. Keep the old schema read-only for the rollback window; drop only after sign-off (§6).

### Step 5 — Run it as a standalone service (1–2 h)
- Deploy the new repo's image next to the monolith, pointing at the new DB. **No traffic yet.** Run smoke + contract tests against it
  (`…HttpClient` against its real `/internal/v1` routes).
- Events: switch its `EventBus` relay from in-process to the broker; publish a shadow stream and verify consumers (still in monolith) receive via a broker-backed subscriber behind a flag.

### Step 6 — Flip consumers (the wiring change, 1–2 h)
In `apps/monolith/wiring.py` (the only file that changes in the monolith):
```python
# before
container.bind(FilesApi, FilesApiImpl(files_module))
# after
container.bind(
    FilesApi, FilesHttpClient(base_url=settings.files_base_url, token_provider=service_token)
)
```
and remove the service from `ENABLED_SERVICES`. Consumers' business code, ports and adapters are untouched.
- Roll out with a **percentage flag** in the wiring (`FILES_ROUTE_PERCENT=5 → 25 → 100`) using a small `WeightedFilesApi` that dispatches to Impl or HttpClient. Compare results/latency; abort by setting to 0.
- Public traffic: add a gateway rule routing `/api/v1/<name>/**` to the new origin (same prefix, so clients don't change). `/internal/**` stays private.

### Step 7 — Cut over events and jobs (1–2 h)
- Producers: outbox relay → broker only (in-process bus off for this service). Consumers: broker subscriptions with dedupe on `event_id`.
- Move the service's scheduled jobs/workers to the new deployment; ensure they're disabled in the monolith (single-run guarantee via `ENABLED_SERVICES`).

### Step 8 — Soak, then clean up (1–2 weeks)
- Watch the service's own SLO burn-rate alerts, error budget, queue lag, DB metrics — dashboards and alerts are the same ones used in the monolith (compare before/after by `app_service`). Keep rollback ready (§6).
- Remove `services/<name>` from the monolith repo **only after** the soak; keep `<name>_contracts` as a dependency (a pinned package) for the remaining consumers.
- Update `ARCHITECTURE.md §5` (service map) and `apps/` (delete `<name>_api`). Record the outcome in the ADR.

---

## 5. Hybrid mode (gradual, safe)

Because wiring is the only seam, the monolith and the extracted service can coexist indefinitely:

```
 monolith (ENABLED_SERVICES=auth,users,notifications)  ──HTTP──►  files-service (own repo, own DB)
                │  broker (events)  ◄─────────────────────────────────┘
```

Never run **two writers** for the same schema: the switch of "who owns the data" is the DB URL cutover in Step 4/6, not a dual-write.

## 6. Rollback

| Until | Rollback |
|---|---|
| Step 6 at <100 % | set route percent to 0; monolith's in-process impl still owns the data |
| After DB cutover | the old schema is read-only but intact: replay writes made since cutover back (from the new DB's outbox/change log) or restore to the pre-cutover dump, flip wiring back, re-enable `ENABLED_SERVICES` |
| After soak sign-off | no rollback; forward-fix only (old schema dropped) |

Define the abort criteria **before** starting (e.g., error rate +0.5 %, p95 +30 %, event lag >60 s for 5 min).

## 7. Time budget (ready service)

| Step | Estimate |
|---|---|
| 1 Freeze/snapshot | 0.5 h |
| 2 New repo + CI | 3 h |
| 3 Infra | 2–4 h |
| 4 Data move (rehearsal + prod) | 3–6 h |
| 5 Standalone deploy + checks | 1–2 h |
| 6 Wiring flip + gradual rollout | 2 h active (+ hours of observation) |
| 7 Events/jobs cutover | 1–2 h |
| **Total active effort** | **≈ 1.5–2.5 days** |

## 8. Staying ready: the quarterly extraction drill

Once per quarter, pick one service and run Steps 2–6 in a **staging** environment against a copy of production data volumes. Measure the time; any step that exceeds
its budget produces a standards fix or tooling improvement. Results are logged in `docs/architecture/ADR/` (drill log).

## 9. Post-extraction obligations

- Its repo adopts the same STANDARDS (layering, contracts versioning, import-linter on its own roots).
- Consumers now depend on a **versioned** `<name>-contracts`; breaking changes follow C-10 with deprecation windows.
- Add: service-level SLOs and alerts, dashboards (already tagged by `service`), runbook in the service README, on-call rotation, per-service CI/CD and secrets.
- Service-to-service auth (service tokens/mTLS) becomes mandatory for `/internal/**`.
