# KT · 01 — Codebase Map

**Goal:** know what every folder and important file is for, so you can find things without searching.
**How to use:** skim once, then keep it open while you read code. **Every path in the first column is checked by `make docs-check`** — if a file is renamed or deleted and this page isn't updated, CI fails (so this map can't silently rot).

> A path containing `<name>` stands for "every service" (e.g. `services/<name>/…`). Services are created by the generator, so none exist yet besides planning docs.

---

## Repository root

| Path | What it is |
|---|---|
| `pyproject.toml` | The **uv workspace root**: lists workspace members (a generated block), dev tools, and settings for ruff, mypy and pytest. No application code lives here |
| `uv.lock` | Exact dependency versions for everyone (committed; CI uses `--frozen`) |
| `.python-version` | Python 3.12 |
| `.importlinter` | **Generated** architecture rules checked by `lint-imports` (never edit by hand) |
| `.env.example` | Every environment variable the local stack reads, with safe local defaults. Copy to `.env` |
| `.dockerignore` | Keeps the Docker build context small and secret-free |
| `.gitignore` | What never gets committed (secrets, caches, local data, generated files) |
| `Makefile` | Everyday commands: `make install lint typecheck test up down new-service …` |
| `docker-compose.yml` | The whole local system (core + `obs` + `tools` profiles); contains generated blocks |
| `README.md` | Project front page: quick start and documentation map |
| `CONTRIBUTING.md` | How to work here day to day: setup loop, branches, commits, PRs |

## `apps/` — composition roots (the only place that knows about several services)

| Path | What it is |
|---|---|
| `apps/monolith/src/monolith_app/main.py` | `create_app()`: sets up observability, discovers services, builds the web app |
| `apps/monolith/src/monolith_app/settings.py` | Process-level settings (`ENABLED_SERVICES`, JWT verification settings) |
| `apps/monolith/src/monolith_app/wiring.py` | Where cross-service ports get bound to providers (empty until a service needs another) |
| `apps/monolith/tests` | Composition tests using fake modules |
| `apps/<name>_api` | *(generated)* runs **one** service alone — used for the extraction drill |

## `libs/` — shared, business-agnostic platform libraries

| Path | What it is |
|---|---|
| `libs/platform_core/src/platform_core/errors.py` | The shared error family (`NotFoundError`, `ConflictError`, …) — HTTP-agnostic |
| `libs/platform_core/src/platform_core/ids.py` | `uuid7()` — time-ordered, strictly increasing IDs |
| `libs/platform_core/src/platform_core/clock.py` | `Clock`, `SystemClock`, `FixedClock` (inject time) |
| `libs/platform_core/src/platform_core/container.py` | The tiny DI container used by composition roots |
| `libs/platform_core/src/platform_core/settings.py` | `PlatformSettings` / `ServiceSettings` bases |
| `libs/platform_core/src/platform_core/health.py` | Health report model aggregated by `/readyz` |
| `libs/platform_core/src/platform_core/db.py` | Async engine/session helpers, schema-aware `MetaData` |
| `libs/platform_core/src/platform_core/pagination.py` | Cursor pagination types |
| `libs/platform_events/src/platform_events/events.py` | `IntegrationEvent` base; event-name convention enforced at import time |
| `libs/platform_events/src/platform_events/bus.py` | `EventBus` port and `InProcessEventBus` |
| `libs/platform_events/src/platform_events/outbox.py` | Transactional outbox: writer, stores (in-memory and SQL), table factory |
| `libs/platform_events/src/platform_events/relay.py` | `OutboxRelay`: moves committed outbox rows to the bus |
| `libs/platform_events/src/platform_events/idempotency.py` | `idempotent()` wrapper for event handlers |
| `libs/platform_http/src/platform_http/module.py` | `ServiceModule` protocol — the single door every service exposes |
| `libs/platform_http/src/platform_http/compose.py` | `create_application()` and `load_modules()` (entry-point discovery) |
| `libs/platform_http/src/platform_http/errors.py` | Uniform error body and handlers |
| `libs/platform_http/src/platform_http/client.py` | Outbound HTTP client with timeouts, safe retries, request-id propagation |
| `libs/platform_security/src/platform_security/verifier.py` | Local JWT verification → `Principal` |
| `libs/platform_security/src/platform_security/keys.py` | Static and JWKS key providers |
| `libs/platform_security/src/platform_security/principal.py` | The authenticated caller model |
| `libs/platform_security/src/platform_security/fastapi_deps.py` | `CurrentPrincipal`, role/permission dependencies |
| `libs/platform_security/src/platform_security/testing.py` | `TestAuth`: throw-away keys and tokens for tests |
| `libs/platform_observability/src/platform_observability/setup.py` | OpenTelemetry SDK bootstrap — the only file touching the SDK/exporters |
| `libs/platform_observability/src/platform_observability/logging.py` | Structured JSON logging with redaction and trace correlation |
| `libs/platform_observability/src/platform_observability/redaction.py` | Secret/PII scrubbing and masking helpers |
| `libs/platform_observability/src/platform_observability/metrics.py` | Counters/histograms with allow-listed attributes |
| `libs/platform_observability/src/platform_observability/tracing.py` | `@traced_use_case`, `@traced_contract_call`, span helpers |
| `libs/platform_observability/src/platform_observability/middleware.py` | Request id, `app.service`, access log, latency metric |
| `libs/platform_observability/src/platform_observability/context.py` | Request-scoped context variables |
| `libs/platform_observability/src/platform_observability/health.py` | `/livez`, `/readyz`, `/startupz` router |
| `libs/platform_observability/src/platform_observability/testing.py` | In-memory spans/metrics for tests |
| `libs/<lib>/tests` | Each library's own tests |

## `services/<name>/` — one folder per service (created by `make new-service`)

| Path | What it is |
|---|---|
| `services/<name>/contracts/` | **Public** package `<name>-contracts` (DTOs, Protocols, events, errors, HTTP client) |
| `services/<name>/service/src/<name>_service/` | **Private** implementation: `api/`, `application/`, `domain/`, `infrastructure/`, `module.py` |
| `services/<name>/service/migrations/` | The service's own Alembic environment |
| `services/<name>/service/tests/` | Module, contract and unit tests |
| `services/<name>/observability/` | `slo.yaml`, alert rules, dashboards, `runbook.md` |
| `services/auth/docs/PLAN.md` | The (not yet built) Auth + RBAC design |

## `tools/` — repository automation

| Path | What it is |
|---|---|
| `tools/new_service.py` | Scaffolds a service (+ standalone app) from `tools/templates/` |
| `tools/templates` | The service scaffold templates (`.tmpl` files rendered by the generator) |
| `tools/sync_workspace.py` | Regenerates workspace members, monolith deps, `.importlinter`, compose blocks, `provision.sql` |
| `tools/sync_observability.py` | Turns each service's `slo.yaml` into alert rules and gathers dashboards |
| `tools/obs_smoke.py` | End-to-end proof that log → trace → metric correlation works |
| `tools/stack_check.sh` | Boots everything with a throw-away service, verifies, tears down |
| `tools/scaffold_check.sh` | Generates a throw-away service and runs every gate on it |
| `tools/list_packages.py` | Lists workspace packages (used by CI and the Makefile) |
| `tools/check_docs.py` | Documentation health check (links, anchors, this map, orphans, chapter sections) |
| `tools/tests` | Tests for the tools themselves |

## `deploy/` and `docker/` — running it

| Path | What it is |
|---|---|
| `docker/Dockerfile` | One multi-stage, non-root image for every app |
| `deploy/postgres/provision.sql` | **Generated**: one role + schema per service |
| `deploy/observability/otel-collector/config.yaml` | The telemetry pipeline (receive → process → export) |
| `deploy/observability/prometheus/prometheus.yml` | Scrape config (exporters, collector) and rule files |
| `deploy/observability/prometheus/rules/platform.rules.yml` | Cause-based platform alerts |
| `deploy/observability/alertmanager/alertmanager.yml` | Alert routing (local default: group, don't send) |
| `deploy/observability/tempo/tempo.yaml` | Trace storage |
| `deploy/observability/loki/loki.yaml` | Log storage |
| `deploy/observability/blackbox/blackbox.yml` | External `/readyz` probe module |
| `deploy/observability/grafana/provisioning/datasources/datasources.yml` | Datasources and the links between signals |
| `deploy/observability/grafana/provisioning/dashboards/dashboards.yml` | Dashboard providers |
| `deploy/observability/grafana/dashboards/red-overview.json` | Rate / Errors / Duration per logical service |
| `deploy/observability/grafana/dashboards/platform-health.json` | Postgres, Redis, collector, probe |

## `.github/` — automation

| Path | What it is |
|---|---|
| `.github/workflows/ci.yml` | Lint, types, architecture, tests per package, scaffold check |
| `.github/workflows/stack.yml` | Nightly/on-demand full stack check (needs Docker) |
| `.github/pull_request_template.md` | The architecture + docs checklist for every PR |
| `.github/CODEOWNERS` | Who must review what |

## `docs/` — documentation

| Path | What it is |
|---|---|
| `docs/architecture/README.md` | Index and the decisions (A1–A20) of the architecture |
| `docs/architecture/ARCHITECTURE.md` | Principles, layout, communication, data ownership |
| `docs/architecture/STANDARDS.md` | The numbered rules and anti-patterns (B/L/D/C/X/O/E/T) |
| `docs/architecture/OBSERVABILITY.md` | Logs/metrics/traces standard, SLOs, alerting |
| `docs/architecture/LOCAL_ENVIRONMENT.md` | How the local compose stack is designed |
| `docs/architecture/EXTRACTION_PLAYBOOK.md` | How to move a service into its own repo |
| `docs/learning/00-INDEX.md` | Entry point of this learning guide |
| `docs/learning/glossary.md` | Every term, in plain English |
| `docs/learning/cheatsheet.md` | Commands, URLs, rules at a glance |
| `docs/learning/troubleshooting.md` | Real errors we hit and their fixes |
| `docs/learning/foundations` | Python, HTTP/FastAPI, databases and testing basics (F·01–04) |
| `docs/learning/phase-a1` | Phase A1 chapters (foundation) |
| `docs/learning/phase-a2` | Phase A2 chapters (Docker, Compose, observability) |
| `docs/learning/kt` | This KT pack: map, reading plan, patterns, diagrams, decisions, debugging, roadmap |
| `docs/learning/assessments` | Question bank, capstone project, skills matrix |
| `docs/learning/templates/chapter-template.md` | The format every chapter follows |

## 🎯 Interview Questions
1. **Where would you look to change how errors are shaped over HTTP?** *`libs/platform_http/src/platform_http/errors.py` (and nowhere in services).*
2. **Where is the only place allowed to wire two services together?** *`apps/*` (for the monolith: `apps/monolith/src/monolith_app/wiring.py`).*
3. **Which files are generated and why must you not edit them?** *`.importlinter`, `deploy/postgres/provision.sql`, the marked blocks in `pyproject.toml`, `apps/monolith/pyproject.toml` and `docker-compose.yml` — they are rewritten from the services on disk, and CI checks they are in sync.*
4. **Where do a service's alerts and dashboards live, and why there?** *`services/<name>/observability/`, so they move with the service on extraction.*

## ✅ Self-check
- [ ] I can say which top-level folder holds shared code, service code, scripts, and deployment files.
- [ ] I can name the four generated files and the command that regenerates them (`make sync`).
- [ ] I know where to find the uniform error handler, the DI container and the outbox relay.

**Next:** [KT · 02 — Reading guide and onboarding plan →](02-reading-guide-and-onboarding-plan.md)
