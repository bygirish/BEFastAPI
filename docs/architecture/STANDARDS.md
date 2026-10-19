# Coding Standards — Patterns & Anti-Patterns

Status: **DRAFT for review** · Applies to every package under `services/`, `libs/`, `apps/` · Last updated: 2026-10-19

These rules exist to keep one promise: **any service can be extracted into its own repo in ≈ 1–2 days**
(see [ARCHITECTURE.md](ARCHITECTURE.md), [EXTRACTION_PLAYBOOK.md](EXTRACTION_PLAYBOOK.md)).

How to use this document
- Every rule has an ID (`B-1`, `L-2`, …). Cite it in reviews: *"violates D-3"*.
- **MUST / MUST NOT** = enforced by CI or a blocking review item. **SHOULD** = default; deviate with a one-line justification in the PR.
- Anti-patterns (§7) are the *named failure modes*; each lists how it is detected.

Companion docs: [OBSERVABILITY](OBSERVABILITY.md) (details behind the O-rules) · [LOCAL_ENVIRONMENT](LOCAL_ENVIRONMENT.md) (details behind the E-rules)

Contents: [1 Boundaries](#1-boundary-rules) · [2 Layering](#2-layering-rules) · [3 Data](#3-data-rules) ·
[4 Communication](#4-communication-rules) · [5 Cross-cutting](#5-cross-cutting-rules) · [6 Code style & testing](#6-code-style-and-testing) ·
[7 Anti-pattern catalogue](#7-anti-pattern-catalogue) · [8 Enforcement](#8-enforcement) · [9 Exceptions process](#9-exceptions-process) ·
[10 PR checklist](#10-pr-checklist) · [11 Documentation is part of Definition of Done](#11-documentation-is-part-of-definition-of-done)

---

## 1. Boundary rules

| ID | Rule |
|---|---|
| **B-1** | A service MUST NOT import another service's implementation package (`<other>_service.*`). The only cross-service import allowed is `<other>_contracts`. |
| **B-2** | `<name>_contracts` MUST be tiny and pure: Pydantic DTOs, `Protocol`s, event models, error types, and the HTTP client. It MUST NOT *directly* import FastAPI, SQLAlchemy or the service implementation. Allowed platform dependencies: `platform_core`, `platform_events` (`IntegrationEvent`), `platform_http` (`ServiceHttpClient`) and `platform_observability` (`traced_contract_call`). |
| **B-3** | `libs/*` MUST NOT import from `services/*` or `apps/*`. `services/*` MUST NOT import from `apps/*`. |
| **B-4** | Only code under `apps/` may reference more than one service's `module.py` or bind ports to providers. |
| **B-5** | Service dependencies form a DAG. A new edge in the service map requires updating `ARCHITECTURE.md §5`; a cycle MUST be broken with an event. |
| **B-6** | A service MUST be runnable and testable alone: `uv run --isolated --package <name>-service pytest services/<name>/service` passes without any other service's code installed (other services replaced by fakes of their ports). |
| **B-7** | Every service MUST declare all its real dependencies in its own `pyproject.toml` (no reliance on packages installed only because a sibling needs them). |
| **B-8** | `libs/*` code MUST be business-agnostic. Promoting code into `libs/` needs: used by ≥3 services, no domain vocabulary, an owner (CODEOWNERS). Otherwise duplicate it. |

**Pattern — "depend on a port you own"**

```python
# services/users/src/users_service/application/ports.py       (Users' own words)
class AvatarStore(Protocol):
    async def get_avatar_url(self, file_id: UUID) -> str | None: ...


# services/users/src/users_service/infrastructure/clients/files_avatar_store.py   (the ONLY place importing files_contracts)
from files_contracts.api import FilesApi


class FilesAvatarStore:
    def __init__(self, files: FilesApi) -> None:
        self._files = files

    async def get_avatar_url(self, file_id: UUID) -> str | None:
        try:
            return (await self._files.get_signed_url(file_id, ttl_s=300)).url
        except FileNotFound:
            return None
```

---

## 2. Layering rules

| ID | Rule |
|---|---|
| **L-1** | Direction is `api → application → domain`; `infrastructure → application.ports + domain`. Nothing points the other way. |
| **L-2** | `domain/` MUST NOT import FastAPI, Pydantic-settings, SQLAlchemy, httpx, redis, vendor SDKs, or `application/infrastructure/api`. It is plain Python (dataclasses / small Pydantic models allowed). |
| **L-3** | `application/` MUST NOT import FastAPI, SQLAlchemy sessions/models, or vendor SDKs. It talks to the outside only through `application/ports.py`. |
| **L-4** | Routers (`api/`) MUST be thin: parse → call one use case → map result/error → return. No business rules, no DB access, no calls to other services. |
| **L-5** | Four model kinds MUST NOT be conflated: HTTP schema (`api/`), domain entity (`domain/`), ORM model (`infrastructure/db/`), contract DTO (`*_contracts`). Map explicitly at each seam. |
| **L-6** | `fastapi.Depends` is allowed only in `api/` (`deps.py`). Use cases receive dependencies through constructors/arguments (plain DI), so they are testable and reusable from handlers/jobs. |
| **L-7** | No module-level mutable state or singletons (engines, clients, caches, settings instances) created at import time. Build them in `module.py`/the composition root and inject. |
| **L-8** | Business logic MUST NOT depend on `Request`, `Response`, `BackgroundTasks`, or any framework object. |

**Pattern — use case with injected ports and a unit of work**

```python
class RegisterUser:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, events: EventPublisher, clock: Clock) -> None: ...
    async def __call__(self, cmd: RegisterUserCommand) -> UserId:
        async with self._uow as uow:
            user = User.register(cmd.identifier, self._hasher.hash(cmd.password), now=self._clock.now())
            await uow.users.add(user)
            uow.outbox.add(UserRegistered(user_id=user.id, ...))     # same transaction (D-5)
            await uow.commit()
        return user.id
```

---

## 3. Data rules

| ID | Rule |
|---|---|
| **D-1** | A table belongs to exactly one service and lives in that service's schema. Only that service reads or writes it. |
| **D-2** | No cross-schema foreign keys, joins, views, triggers, or shared tables. Refer to other services' entities by opaque ID only. |
| **D-3** | Each service has its own Alembic environment, version table (in its schema), and `<NAME>_DATABASE_URL`. A migration MUST NOT touch another schema. |
| **D-4** | Each service connects with its own DB role granted only its schema (enforced outside local dev). |
| **D-5** | State changes that others care about publish an event through the **transactional outbox** in the same transaction as the data change. Never "write DB, then publish" in two steps. |
| **D-6** | Transactions never span services. Cross-service consistency is eventual (events / saga with compensations). |
| **D-7** | Need another service's data often? Keep a **local read-model** fed by events (or a cached batched call), not a join and not a call-per-row. |
| **D-8** | Redis keys, queues, streams, and object-storage prefixes are namespaced by service (`<name>:…`). |
| **D-9** | IDs are UUIDv7/ULID generated by the owning service; never auto-increment integers exposed outside the service. |
| **D-10** | Timestamps are timezone-aware UTC; obtained via an injected `Clock`. |

---

## 4. Communication rules

| ID | Rule |
|---|---|
| **C-1** | Sync calls to another service go through a **consumer-owned port** + adapter (§1 pattern). Calling `…Impl` or an HTTP URL directly from a use case is forbidden. |
| **C-2** | Contract methods take and return DTOs only (JSON-serialisable). No ORM objects, sessions, entities, `UploadFile`, generators, or callables. |
| **C-3** | Contract methods are coarse-grained and batchable; lists are paginated; commands that may be retried carry an idempotency key. |
| **C-4** | Design every call as if remote: handle `Unavailable`/`Timeout`; the in-process implementation MUST raise the same contract errors as the HTTP client. |
| **C-5** | Max **one hop**: while serving request A→B, B MUST NOT synchronously call C. Use events/read-models. |
| **C-6** | Events: past-tense facts, named `<service>.<noun>_<verb>.v<N>`, defined only in `*_contracts.events`, carrying IDs + minimal fields, with `event_id`, `occurred_at`, `correlation_id`. |
| **C-7** | Event handlers MUST be idempotent (dedupe by `event_id`) and MUST NOT assume ordering across aggregates. |
| **C-8** | Event schemas evolve additively within a version. Breaking change ⇒ publish `.v2` alongside `.v1` until all consumers migrate. |
| **C-9** | Don't use events as RPC (publish → wait for reply event inside a request). If you need an answer now, make a call. |
| **C-10** | Contract changes follow: additive-only within a major; deprecate → announce → remove after ≥1 release; contract tests run against both in-process and HTTP implementations. |

---

## 5. Cross-cutting rules

| ID | Rule |
|---|---|
| **X-1** | **AuthN**: other services verify JWTs locally via `platform_security`; they MUST NOT import Auth internals or call Auth per request to validate a token. |
| **X-2** | **AuthZ**: each service checks permissions for its own resources using the `Principal`; org-scoped checks use the token's active `org`. Never trust an `org_id`/`user_id` from the request body when it can be taken from the `Principal`. |
| **X-3** | **Errors**: domain raises domain errors; `api/` maps them to the uniform error body; codes are service-prefixed (`FILES_QUOTA_EXCEEDED`). Never leak stack traces, SQL, or vendor messages. |
| **X-4** | **Config**: `<NAME>_`-prefixed `BaseSettings` per service; never read another service's env/settings; fail fast on invalid/unsafe combos. |
| **X-5** | **Logging**: structured JSON with `service`, `request_id`, `trace_id`; never log secrets, tokens, passwords, OTPs, full PII. |
| **X-6** | **Tracing**: propagate `X-Request-ID` + `traceparent` on every outbound HTTP call and in event metadata. |
| **X-7** | **Third-party vendors** are hidden behind a port in `infrastructure/providers`; business code never imports a vendor SDK. |
| **X-8** | **Background jobs** are owned by one service, registered via `module.py`, idempotent, and named/queued with the service prefix. |
| **X-9** | **Internal endpoints** (`/internal/v1/*`) require a service principal and are excluded from public gateway routes. |
| **X-10** | **Feature flags / settings** that change behaviour per environment come from settings, never from `if ENV == "prod"` scattered in code (one validated check at startup is fine). |
| **X-11** | **Dev-only adapters refuse to start in production.** An adapter or endpoint that exists for development (console/in-memory/static senders, `*_DEV_ENDPOINTS`, default peppers/secrets) is checked by a validated settings rule at start-up: `ENV=production` + any of them ⇒ the process exits with a clear message. They are the *only* code allowed to print message bodies or recipients (a documented exception to X-5/O-4), and they must be listed in the service's `DEV_ONLY_PROVIDERS`-style constant and covered by a test. |
| **O-1** | Telemetry uses the **OpenTelemetry API** and OTLP only. SDK/exporters live solely in `platform_observability`. No vendor agents/SDKs (Datadog, New Relic, Sentry init…) in service code. `opentelemetry-api` is allowed in `api/`, `application/`, `infrastructure/`; **not** in `domain/`. |
| **O-2** | Logs are structured JSON via the platform logger: constant snake_case `event`, data in fields (no f-string messages), OTel attribute names, `trace_id`/`span_id`/`request_id` injected automatically. `print()` is banned. |
| **O-3** | **Log once, at the boundary** (HTTP handler, job runner, event-handler wrapper). Don't log-and-raise in inner layers. |
| **O-4** | Never emit secrets or PII (passwords, OTPs, tokens, auth headers, raw email/phone, request bodies) to logs, spans or metrics. Use IDs or masked values. Redaction processors are mandatory and not bypassable. |
| **O-5** | Metric attributes come from **closed enumerations** declared with the instrument (allow-list). No user/org/session IDs, URLs, emails, IPs, error text. Names are dotted `<service>.<noun>[.<verb>]` with base units. |
| **O-6** | Every use case is wrapped in a span (`@traced_use_case`); every cross-service adapter call has a CLIENT span (same name in-process and over HTTP); outbox rows carry `traceparent` and consumers use span **links**. |
| **O-7** | `app.service` is stamped on every signal by the platform — never set by hand. |
| **O-8** | Each service ships `observability/` (`slo.yaml`, alert rules, dashboards, `runbook.md`, README with metric/log/span catalog). CI lints it; an alert without a runbook section fails the build. |
| **O-9** | Page on **SLO burn rate** (multi-window, multi-burn-rate). Cause-based alerts (CPU, queue age, pool saturation) need a one-line justification in the alert annotations. |
| **O-10** | Health endpoints `/livez`, `/readyz`, `/startupz` come from the platform builder; `readyz` aggregates each enabled module's `health()`. |
| **O-11** | Telemetry MUST NOT block or fail a request: batched async export, bounded queues, drop-and-count on failure. |
| **O-12** | RED metrics are automatic. Add business metrics only when a business question or SLO needs them, and document them in the service's observability README. |
| **E-1** | Every service runs from the root `docker-compose.yml`. Adding a service goes through `tools/new_service.py`, which adds its schema+role init, `migrate-<svc>` job and `ENABLED_SERVICES` entry. No hand-edited per-service special cases. |
| **E-2** | One Dockerfile pattern for all apps: multi-stage, non-root, `HEALTHCHECK` on `/readyz`, graceful SIGTERM (drain + flush telemetry). Image versions are pinned — no `latest`. |
| **E-3** | Configuration only via environment variables; `.env.example` documents every variable; no secrets in compose files or images. |
| **E-4** | Start-up ordering uses health/completion conditions, never `sleep`. Migrations run as one-shot per-service jobs before the app starts. |
| **E-5** | The local observability stack uses the same OTLP/Collector configuration shape as production; only backends differ. |
| **E-6** | `make test s=<service>` must work without compose (unit) and may use testcontainers (integration). |

---

## 6. Code style and testing

| ID | Rule |
|---|---|
| **S-1** | Python 3.12, `async` end-to-end for I/O; no blocking calls in request paths (use `run_in_executor` for CPU/blocking libs such as hashing). |
| **S-2** | `mypy --strict` clean for `domain/`, `application/`, `contracts`, `libs`; typed everywhere else (`ruff` ANN rules). No bare `Any` in contracts. |
| **S-3** | `ruff` (lint + format) is the single style authority; no per-developer overrides. |
| **S-4** | Absolute imports from the package root (`from users_service.application...`), never relative imports that climb out of a layer (`from ...`). |
| **S-5** | Public surface of a layer is explicit (`__all__` or an `__init__` re-export); everything else is private by convention (`_name`). |
| **S-6** | Prefer small, explicit classes/functions over inheritance hierarchies; composition over inheritance; no "base service" god classes. |
| **S-7** | Names: modules `snake_case`, use cases are verbs (`RegisterUser`, `ListInvoices`), events are past-tense, ports are nouns (`AvatarStore`, `Clock`). |
| **T-1** | Unit tests use fakes for ports; no network, no DB, no sleeping. Time and IDs are injected. |
| **T-2** | Integration tests use real Postgres/Redis (testcontainers) and exercise the service through its HTTP API or use cases. |
| **T-3** | Every `contracts.api` has a **shared contract test suite** parametrised over `…Impl` and `…HttpClient`. |
| **T-4** | Every consumer adapter (`infrastructure/clients/*`) is tested against a fake of the provider's contract. |
| **T-5** | Security-sensitive modules (tokens, OTP, lockout, RBAC) require negative tests (replay, expiry, escalation, cross-org access). |
| **T-6** | A PR that adds a service-to-service edge MUST add/modify an architecture test or doc entry proving the edge is declared. |
| **T-7** | Tests live inside their service (`services/<name>/tests`); cross-service end-to-end tests live under `apps/monolith/tests`. |
| **T-8** | Telemetry tests per service: secrets/OTP/PII never appear in logs/spans/metrics (redaction test); metric attributes ⊆ allow-list; a request yields a server span + use-case span + correlated log line + RED metric (telemetry contract test). |

---

## 7. Anti-pattern catalogue

Each entry: **symptom → why it blocks extraction → do this instead → detection**.

| ID | Anti-pattern | Why it hurts | Do instead | Detection |
|---|---|---|---|---|
| **AP-01** | **Deep import** — `from auth_service.infrastructure.db.models import User` in another service | Extraction breaks every importer; hidden coupling to internals | Import `auth_contracts` only; use a port (B-1, C-1) | import-linter `independence` contract |
| **AP-02** | **Shared database access** — querying another service's table (even read-only) | The other service can never change or move its schema | Call its contract or keep a read-model from events (D-1, D-7) | DB role grants; `check_db_isolation.py`; review |
| **AP-03** | **Cross-schema FK / join / view / trigger** | Makes DB split impossible without rewrite | IDs only; eventual consistency (D-2) | migration linter scanning for `REFERENCES other_schema` |
| **AP-04** | **`common/`, `utils/`, `shared/models` dumping ground** | Becomes a hidden shared kernel with business concepts; every change ripples | Keep `libs/*` technical; duplicate small helpers (B-8) | CODEOWNERS on `libs/`; ruff banned module names; review |
| **AP-05** | **ORM model leaking** — returned from API, put in events, or used as contract DTO | Couples wire format to table design; lazy-loading explodes remotely | Map to HTTP schema / contract DTO (L-5, C-2) | mypy + review; contracts can't import SQLAlchemy |
| **AP-06** | **Business logic in routers** | Can't be reused by handlers/jobs; untestable without HTTP | Move to `application/` use case (L-4) | review; router size/complexity lint |
| **AP-07** | **Framework in the domain** (FastAPI/SQLAlchemy/httpx imports in `domain` or `application`) | Domain can't move or be tested in isolation | Ports + adapters (L-2, L-3) | import-linter `layers` contract |
| **AP-08** | **Distributed monolith** — A calls B calls C synchronously per request | One slow service stalls all; extraction multiplies latency | ≤1 hop; events + read-models (C-5) | review; tracing span-depth alert |
| **AP-09** | **Chatty calls / N+1 across services** (loop calling `get_user(id)`) | Cheap in-process, catastrophic over network | Batch contract methods (C-3) | review; call-count assertions in tests |
| **AP-10** | **Event-as-RPC / fat events / events with entities** | Hidden temporal coupling; schema becomes the shared model | Facts with IDs + minimal fields; use calls for questions (C-6, C-9) | review; event model lint (max fields, no nested entities) |
| **AP-11** | **Cyclic dependency** (A→B and B→A, directly or through contracts) | Neither can be deployed or versioned alone | Invert via event; extract shared concept to a third service or merge (B-5) | import-linter cycle check; service-map test |
| **AP-12** | **Global singletons / import-time side effects** (`engine = create_engine(...)` at module top, `settings = Settings()` imported everywhere) | Cannot run several services in one process or configure per-mode | Factories + DI in `module.py` (L-7) | ruff rule for module-level calls in layers; review |
| **AP-13** | **Reading another service's settings/env** or hardcoding its URL | Config coupling; breaks on move | Own settings + adapter config in wiring (X-4) | import-linter; grep for foreign env prefixes |
| **AP-14** | **Cross-service transaction** (shared session / `begin()` across services) | Impossible to preserve once split | Outbox + saga/compensation (D-5, D-6) | no session in contracts; review |
| **AP-15** | **In-process assumptions** — passing mutable objects, relying on shared memory/caches, raising unmapped exceptions across a call | Works in monolith, fails when remote | Treat as remote (C-4); same errors in both impls | contract test suite on both impls; latency/fault injection in tests |
| **AP-16** | **Auth coupling** — calling Auth per request to validate a token, or importing Auth's `User` | Auth becomes a runtime SPOF and a code dependency | Local JWT verify via `platform_security` (X-1) | import-linter; review |
| **AP-17** | **Vendor SDK in business code** (Twilio/boto3 imports in use cases) | Vendor swap touches core logic | Port + provider adapter (X-7) | import-linter forbidden imports |
| **AP-18** | **God service class** (`UserService` with 40 methods spanning contexts) | Boundaries inside a service blur; later splits are painful | One use case per verb; cohesive groups (S-6) | file-size / method-count lint |
| **AP-19** | **Hidden coupling via shared constants/enums/exceptions** imported from another service | A "harmless" enum import becomes a dependency | Put it in that service's `*_contracts`, or redefine locally | import-linter (B-1) |
| **AP-20** | **Unnamespaced shared infra** — same Redis keys, queue names, S3 prefixes across services | Collisions and impossible-to-split state | Prefix by service (D-8) | key-naming lint in `platform_core` helpers |
| **AP-21** | **Premature microservice** — extracting without a trigger | Operational cost with no benefit | Follow playbook §2 triggers | ADR required for any extraction |
| **AP-22** | **"Temporary" boundary exception without owner/expiry** | Exceptions become the architecture | ADR with expiry date (§9) | `import-linter` ignore list must reference ADR IDs |
| **AP-23** | **Test-only coupling** — tests of service A importing service B's fixtures/factories | A can't be tested alone after the split | Fakes of ports in A's tests; contract tests (B-6, T-1) | per-service test run in CI |
| **AP-24** | **Shared Alembic history / one giant migration chain** | Can't move one schema's history | Per-service Alembic (D-3) | CI runs each service's migrations alone on an empty DB |
| **AP-25** | **Leaky pagination/filter language** — exposing raw SQL-ish filters or ORM field names in contracts | Locks provider's storage design | Stable, documented query params in DTOs | review |
| **AP-26** | **Trusting client-supplied identity** (`user_id`/`org_id` in body used for authorization) | Cross-tenant data leaks, worse when services multiply | Derive from `Principal` (X-2) | security tests (T-5) |
| **AP-27** | **High-cardinality metric labels** (user_id, raw URL, error message, email) | Explodes time-series count; cost and instability; makes metrics unusable | Closed enumerations; put IDs on traces/logs (O-5) | instrument allow-list test; Prometheus series limit |
| **AP-28** | **PII/secrets in telemetry** (OTP in a log line, token in a span attribute, email as metric label) | Security/compliance incident; telemetry is widely readable and long-lived | Masked identifiers; redaction processors (O-4) | redaction test (T-8); Collector safety-net; gitleaks |
| **AP-29** | **Unstructured or duplicate logging** (`print`, f-string messages, log-and-raise at every layer) | Unqueryable logs, noise, duplicate alerts, no correlation | Constant `event` + fields; log once at boundary (O-2, O-3) | ruff `T20`; custom check; review |
| **AP-30** | **Vendor lock-in in app code** (direct Datadog/Sentry/NewRelic SDK calls, backend URLs in services) | Changing the observability vendor means touching every service | OTel API + Collector (O-1) | import-linter forbidden imports |
| **AP-31** | **Alerting on causes, not symptoms** (CPU > 80 %, "any error log"), or alerts with no runbook | Alert fatigue, missed real user impact | SLO burn-rate alerts + runbooks (O-8, O-9) | rules lint in CI |
| **AP-32** | **Telemetry in the critical path** (synchronous exporters, awaiting collector, unbounded queues) | Observability outage becomes a product outage | Async batched export, drop-and-count (O-11) | fault-injection test: collector down |
| **AP-33** | **Compose/infra drift** (hand-edited per-service compose entries, `sleep` for ordering, `latest` tags, secrets in compose, app that only works in one environment) | "Works on my machine"; extraction rehearsal impossible | Generator-managed entries, health-based ordering, pinned images, env-only config (E-1…E-5) | `make up` in CI; compose lint; image-pin check |

---

## 8. Enforcement

Rules without tooling decay. These run in CI on every PR (`.github/workflows/architecture.yml`).

### 8.1 import-linter (`.importlinter`) — GENERATED

The real config is generated from the services on disk by `tools/sync_workspace.py` (CI runs it with `--check`), so a new service gets its contracts automatically and nobody edits `.importlinter` by hand. The excerpt below is illustrative; see the generated file for the exact contracts. Layer names inside a service are relative to the container package (`api | infrastructure` > `application` > `domain`).

```ini
[importlinter]
root_packages =
    auth_service
    auth_contracts
    users_service
    users_contracts
    files_service
    files_contracts
    notifications_service
    notifications_contracts
    platform_core
    platform_events
    platform_http
    platform_security
    platform_observability
    monolith_app

# B-1 / AP-01 / AP-19: implementation packages are independent of each other
[importlinter:contract:services-independent]
name = Services must not import each other's implementation
type = independence
modules =
    auth_service
    users_service
    files_service
    notifications_service

# B-1: only contracts may be imported across services (consumers → other contracts is allowed, internals is not)
[importlinter:contract:no-foreign-internals]
name = users_service may only use contracts of other services
type = forbidden
source_modules = users_service
forbidden_modules =
    auth_service
    files_service
    notifications_service

# B-2: contracts are pure
[importlinter:contract:contracts-pure]
name = Contracts are framework- and implementation-free
type = forbidden
source_modules =
    auth_contracts
    users_contracts
    files_contracts
    notifications_contracts
forbidden_modules =
    fastapi
    sqlalchemy
    auth_service
    users_service
    files_service
    notifications_service

# B-3: libs know nothing about services
[importlinter:contract:libs-independent]
name = libs must not import services
type = forbidden
source_modules = platform_core platform_events platform_http platform_security platform_observability
forbidden_modules =
    auth_service
    users_service
    files_service
    notifications_service

# L-1..L-3 / AP-07: layering inside each service (one contract per service, generated by tools/new_service.py)
[importlinter:contract:users-layers]
name = users_service layering
type = layers
layers =
    users_service.api
    users_service.application
    users_service.domain
containers = users_service
exhaustive = false

[importlinter:contract:users-domain-pure]
name = users_service domain/application are framework-free
type = forbidden
source_modules =
    users_service.domain
    users_service.application
forbidden_modules =
    fastapi
    sqlalchemy
    httpx
    redis
    users_service.infrastructure
    users_service.api
```

New services get their contracts appended by `tools/new_service.py`; the generator is the reason adding a service is cheap.

### 8.2 Other checks

| Check | Tool | Rules covered |
|---|---|---|
| Rules/dashboards lint (`promtool check rules`, Grafana JSON validity, runbook anchors), telemetry contract tests, `make obs-smoke` nightly | `promtool`, pytest, `tools/obs_smoke.py` | O-6, O-8, O-9, T-8, AP-27…AP-32 |
| Compose lint & boot test (`docker compose config`, image-pin check, `make up` healthy in CI nightly) | `docker compose`, script | E-1…E-5, AP-33 |
| Lint, format, banned APIs (`ruff` with `flake8-tidy-imports` banned-api, no `utils.py`/`common.py` names, no module-level calls in layers) | `ruff` | S-3, S-4, AP-04, AP-12 |
| Strict types on domain/application/contracts/libs | `mypy` | S-2, AP-05 |
| DB isolation: scans models/migrations for cross-schema references; verifies per-service roles in the integration DB | `tools/check_db_isolation.py` | D-1..D-4, AP-02/03/24 |
| Each service tested alone (workspace-scoped run, other services *not installed*) | CI matrix `uv run --package <svc> pytest` | B-6, B-7, AP-23 |
| Contract tests on both implementations | pytest suite in `*_contracts/testing` | C-4, T-3, AP-15 |
| **Extraction drill**: start `apps/<svc>_api` with other ports bound to fakes; smoke-test; run service's migrations on an empty DB | `tools/extraction_drill.py` (nightly + PRs touching a service) | B-4, B-6, D-3 |
| Event model lint (naming, version suffix, required metadata, no nested entities) | pytest in `platform_events` | C-6, C-8, AP-10 |
| Service-map consistency (declared edges == real import edges between services/contracts; no cycles) | `tools/check_service_map.py` | B-5, AP-11 |
| CODEOWNERS: each `services/<name>` has an owner; `libs/` and `docs/architecture` need architecture-owner approval | GitHub | B-8, AP-04 |

---

## 9. Exceptions process

1. Open an ADR in `docs/architecture/ADR/NNNN-<slug>.md`: rule ID being waived, reason, risk, **owner**, **expiry date**, removal plan.
2. Reference the ADR ID next to the suppression (`# noqa`, import-linter `ignore_imports`, grant exception).
3. CI fails when an exception is past its expiry.
4. Exceptions are reviewed in the quarterly extraction drill retro.

Allowed without ADR: test-only fixtures inside the same service; generated code; `apps/` wiring that is by definition cross-service.

---

## 10. PR checklist

Copy into `.github/pull_request_template.md`:

- [ ] No import of another service's internals (only `*_contracts`) — B-1
- [ ] No new cross-service edge, or `ARCHITECTURE.md §5` + service-map check updated — B-5
- [ ] No cross-schema SQL/FK; new tables are in this service's schema; migration is in this service's Alembic — D-1..D-3
- [ ] State change + event written via outbox in one transaction — D-5
- [ ] New/changed contract is additive; contract tests cover both implementations — C-10, T-3
- [ ] Sync calls to other services go through a port; batched; ≤1 hop; failures handled — C-1..C-5
- [ ] Routers thin; logic in use cases; framework-free domain/application — L-2..L-4
- [ ] Identity/org derived from `Principal`, never from client input — X-2
- [ ] No secrets/PII/OTP in logs; errors use the uniform body with a service-prefixed code — X-3, X-5
- [ ] Tests run for this service alone; negative/security tests added where relevant — B-6, T-5
- [ ] Any rule waiver has an ADR with owner + expiry — §9
- [ ] Learning docs: the phase's chapter in `docs/learning/` is added/updated (commands actually run, links checked), and new terms/commands/errors are in the glossary, cheat-sheet and troubleshooting page — see §11

---

## 11. Documentation is part of Definition of Done

Every phase ships **two kinds of docs**:

| Kind | Folder | Audience | Purpose |
|---|---|---|---|
| Specifications | `docs/architecture/` | engineers making decisions | the rules and the reasoning (authoritative) |
| Learning guide | `docs/learning/` | **beginner developers** (study, onboarding, KT) | teaches the ideas with analogies, diagrams, runnable examples, traps, interview questions and labs |

A phase is **not done** until: (1) its chapter(s) exist, written from `docs/learning/templates/chapter-template.md`; (2) every ▶ command was run and its output pasted from reality;
(3) external links were checked; (4) `docs/learning/00-INDEX.md`, the glossary, cheat-sheet, troubleshooting page, codebase map and question bank are updated; (5) bugs found while documenting are fixed and covered by a test; (6) `make docs-check` is green (broken links/anchors, stale paths in the codebase map, orphan pages and missing chapter sections fail CI).
