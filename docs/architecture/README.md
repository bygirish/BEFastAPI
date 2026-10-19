# Architecture Documentation — BEFastAPI

Status: **ACCEPTED — decisions A1–A20 confirmed 2026-10-19** · Last updated: 2026-10-19

A modular FastAPI monolith where **each service (Auth, Users, Files, Notifications, …) is built to be lifted out into its own
repo and deployed separately with ≈ 1–2 days of mechanical work.**

| Doc | Read it for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Principles, repo layout, anatomy of a service, service map, communication (calls + events), data ownership, identity, deployment modes, testing architecture |
| [STANDARDS.md](STANDARDS.md) | Numbered rules (B/L/D/C/X/S/T), 33 named anti-patterns with detection, CI enforcement (import-linter etc.), exceptions process, PR checklist |
| [OBSERVABILITY.md](OBSERVABILITY.md) | OpenTelemetry pipeline, logging/metrics/tracing standards, SLOs & burn-rate alerts, dashboards, redaction, how observability is tested and how it survives extraction |
| [LOCAL_ENVIRONMENT.md](LOCAL_ENVIRONMENT.md) | Docker Compose design: every service + DB + Redis + observability stack + dev tools via one `docker compose up`; Makefile workflow; acceptance criteria |
| [EXTRACTION_PLAYBOOK.md](EXTRACTION_PLAYBOOK.md) | When to extract, readiness scorecard, step-by-step cutover, hybrid mode, rollback, time budget, quarterly drill |
| [Learning guide for beginners](../learning/00-INDEX.md) | Study / onboarding / KT chapters per phase: analogies, diagrams, runnable examples, traps, interview questions, labs |
| [Auth plan](../../services/auth/docs/PLAN.md) | Detailed Auth + RBAC design (re-homed into this structure; see ARCHITECTURE §14) |

> **New here?** Start with the [Learning guide](../learning/00-INDEX.md). These architecture docs are the *specification*; the learning guide *teaches* them.

## The design in eight lines

1. `services/<name>/` is one future repo: own `pyproject.toml`, own DB schema + Alembic, own settings, own Dockerfile.
2. Each service has a tiny public **`<name>_contracts`** package (DTOs, Protocols, events, errors, HTTP client). Everything else is private.
3. Consumers define a **port** in their own words; an adapter binds it to the provider's contract — in-process today, HTTP after extraction.
4. State changes publish **versioned events via a transactional outbox**; in-process bus today, broker later.
5. **`apps/`** is the only place that wires services together; extraction = change one binding + move one schema.
6. **Observable by default**: OpenTelemetry traces/metrics/logs correlated end-to-end; SLOs, alerts and dashboards live inside each service folder.
7. **One command locally**: `docker compose up` runs every service, databases, migrations and the observability stack.
8. **CI enforces it** (import-linter, DB-isolation check, per-service test runs, extraction drill).

## Decisions (proposed defaults — please confirm or change)

| # | Decision | Proposed default | Alternative |
|---|---|---|---|
| A1 | Folder for services | Keep `services/<name>` (already in repo) | `modules/` |
| A2 | Packaging | **uv workspace**, one `pyproject.toml` per service/contracts/lib | single root `pyproject.toml` (cheaper now, costlier to extract) |
| A3 | Contracts packaging | Separate **`<name>_contracts`** package per service | `contracts/` subpackage inside the service package (simpler, weaker enforcement) |
| A4 | DB isolation | One Postgres, **schema + role per service**, own Alembic each | one shared schema (rejected: blocks extraction) |
| A5 | Events | **Transactional outbox from day one**, in-process bus now, broker (Redis Streams/NATS/Kafka/SQS) chosen at first extraction | direct in-memory publish only (rejected: hides at-least-once bugs) |
| A6 | Sync inter-service calls | Consumer-owned **port + adapter**; coarse-grained, ≤1 hop | direct imports of provider (rejected) |
| A7 | Auth / Users boundary | Auth = credentials, identities, sessions, orgs, RBAC; **Users = profile** (display name, avatar, locale, timezone) | profile fields stay in Auth |
| A8 | OTP responsibility | **Auth owns OTP code/verification + static-OTP test mode; Notifications owns delivery** (the vendor-neutral facade moves there) | Facade stays inside Auth |
| A9 | Token verification elsewhere | Local JWT verification via `libs/platform_security` + JWKS | call Auth per request (rejected) |
| A10 | Public route shape | `/api/v1/<service>/…` (gateway-routable); `/internal/v1/<service>/…` for service-to-service | single flat namespace |
| A11 | Enforcement tooling | `import-linter`, `ruff` (banned-api), `mypy --strict` on core layers, custom DB-isolation & service-map checks | docs-only (rejected) |
| A12 | Repo strategy after extraction | Mono-repo now → polyrepo per extracted service; `libs/*` + contracts published to a private index at first extraction | stay mono-repo with separate deploys (also viable; the playbook works for both) |
| A13 | Telemetry standard | **OpenTelemetry** (API/SDK/OTLP) for traces, metrics, logs; Collector in front of all backends | vendor agent (rejected: lock-in) |
| A14 | Local/default observability backends | **Grafana stack**: Tempo (traces), Prometheus (metrics + exemplars), Loki (logs), Grafana, Alertmanager; optional Pyroscope | Jaeger/ELK; hosted vendor later by Collector config only |
| A15 | Observability assets location | **Inside each service** (`services/<name>/observability/`: SLOs, alert rules, dashboards, runbook) | central folder (rejected: doesn't travel on extraction) |
| A16 | Alerting philosophy | **SLO multi-window burn-rate** alerts generated from `slo.yaml`; cause alerts by exception | threshold alerts only (rejected) |
| A17 | Logical service identity in telemetry | `app.service` on every signal in addition to OTel `service.name` | rely on `service.name` only (breaks in the monolith) |
| A18 | Compose design | One root `docker-compose.yml` with **profiles** (core, `obs`, `tools`, later `split`); `.env` sets `COMPOSE_PROFILES=obs,tools` so `docker compose up` starts everything | separate compose files per concern |
| A19 | Migrations in compose | **One-shot `migrate-<svc>` job per service** (own Alembic) gating app start | app runs migrations on boot (rejected: races, blocks extraction) |
| A20 | Split-mode rehearsal | Reserve `split` profile (per-service containers + Redis-Streams broker + prefix gateway); **build after ≥2 services have HTTP clients** (Roadmap F) | build now (premature) |

## Roadmap (no code yet)

Order matters: structure and guardrails first, then services from leaf to root of the dependency graph.

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **A1. Foundation** ✅ *(done 2026-10-19; learning chapters 01–08 in `docs/learning/phase-a1/`)* | uv workspace; libs `platform_{core,events,http,security,observability}` skeletons; `apps/monolith` with `/livez` `/readyz` `/startupz`; `ServiceModule` protocol; ruff/mypy/import-linter config; `tools/new_service.py` (generates service **incl. contracts, migrations, tests, Dockerfile entry, `observability/` folder**, adds compose + init entries); PR template; CODEOWNERS; CI | `new_service.py demo` produces a service that passes all CI checks and the extraction drill |
| **A2. Local env & observability** | `docker/Dockerfile`; root `docker-compose.yml` (core + `obs` + `tools` profiles); Postgres init (schema+role per service); `keygen`, `migrate-<svc>` jobs; Collector, Prometheus, Tempo, Loki, Alertmanager, Grafana **provisioned with trace↔log↔metric correlation**; exporters + blackbox probes; base dashboards; `tools/gen_slo_rules.py`; Makefile; `tools/obs_smoke.py` | `cp .env.example .env && docker compose up` → all healthy ≤3 min; demo request visible as correlated trace/logs/metrics in Grafana; `make obs-smoke`, `make drill s=demo`, `make lint` green |
| **B. Notifications v0** | `notifications` service: gateway/facade, Static/Console/InMemory senders, `NotificationsApi.send`, delivery log | contract tests pass on Impl + HttpClient; no dependency on other services |
| **C. Auth** | Auth plan phases 0–6 mapped into the layer layout; `OtpDelivery` port → Notifications; JWKS; org-scoped RBAC | Auth runs standalone via `apps/auth_api`; extraction drill green |
| **D. Users** | profile service reacting to `auth.user_registered.v1`; `UsersApi.get_profiles(ids)` | no import of Auth internals; event handler idempotency tests |
| **E. Files** | metadata, upload sessions, signed URLs, storage provider port (S3/local) | avatar flow Users→Files through a port |
| **F. Split rehearsal & first drill** | build compose `split` profile (broker bus, HTTP clients, gateway); run the extraction drill on Notifications | measured against the playbook time budget; findings folded into STANDARDS; dashboards/alerts unchanged after the flip |

Auth Phases 0–6 re-sequence: scaffolding is covered by Phases A1–A2; **Auth Phase 2 (OTP + facade) is split** — the OTP code logic stays in Auth, the delivery facade is built in Phase B.

## Glossary

- **Service**: a business capability with its own code, data, contract, and config. Today a folder; tomorrow possibly a repo/deployment.
- **Contract**: the public, versioned surface of a service (`<name>_contracts`): DTOs, `Protocol`s, events, errors, HTTP client.
- **Port / adapter**: a consumer-owned interface for what it needs / the implementation that binds it to a provider or vendor.
- **Composition root**: `apps/*` — the only place where services are wired together.
- **Outbox**: a table written in the same transaction as a state change, relayed to the event bus afterwards.
- **Principal**: the authenticated caller (user or service) decoded from a verified JWT.
- **Extraction drill**: automated check that a service boots, migrates, and passes smoke tests alone.
