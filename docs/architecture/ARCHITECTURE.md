# Architecture — Extraction-Ready Modular Monolith

Status: **DRAFT for review** · Python 3.12 + FastAPI · Last updated: 2026-10-19

> **The one rule:** *design every service as if it were already remote; deploy them as if they were one process.*
>
> Everything below exists to make that sentence cheap to obey. If a rule here ever conflicts with convenience, the rule wins
> or an ADR records the exception (see [STANDARDS.md §9](STANDARDS.md#9-exceptions-process)).

Related docs: [README (index & decisions)](README.md) · [STANDARDS (patterns & anti-patterns)](STANDARDS.md) ·
[EXTRACTION_PLAYBOOK](EXTRACTION_PLAYBOOK.md) · [Auth service plan](../../services/auth/docs/PLAN.md)

---

## 1. Goals and non-goals

**Goals**
1. Ship fast now: one repo, one deployable, one Postgres, one local `docker compose up`.
2. Keep each business capability (Auth, Users, Files, Notifications, …) behind a hard boundary.
3. Be able to lift any service into its own repo and deploy it separately in **≈ 1–2 engineer-days**, with **no change to
   other services' business code** (only to wiring/config).
4. Make the boundary rules **machine-enforced** (CI fails), not just documented.

**Non-goals**
- Running microservices from day one (no service mesh, no Kubernetes requirement, no broker required today).
- A perfect domain model up front. Boundaries are chosen conservatively; they can be merged or split as we learn.
- Reuse through a big shared "common" package. Duplication of small things across services is cheaper than coupling.

---

## 2. Principles

| # | Principle | Practical meaning |
|---|---|---|
| P1 | **Own your data** | A service is the only reader/writer of its tables. Others use its public contract. |
| P2 | **Public contract, private everything else** | Each service exposes a tiny `*_contracts` package. All other code is private. |
| P3 | **Depend on ports, not services** | A consumer defines the interface it needs; an adapter binds it to the provider (in-process today, HTTP tomorrow). |
| P4 | **Wiring lives in one place** | Only the composition root (`apps/`) knows which services exist and how they connect. |
| P5 | **Assume remote semantics** | Calls can fail, be slow, be retried; payloads are DTOs; no shared sessions, no lazy loading across boundaries. |
| P6 | **Events for facts, calls for questions/commands** | Don't use events as hidden RPC; don't chain sync calls (that's a distributed monolith). |
| P7 | **Dependency graph is a DAG** | No cycles between services. Cycles are broken with events. |
| P8 | **Enforce by tooling** | `import-linter`, `ruff`, `mypy`, DB-grant checks and an "extraction drill" test run in CI. |
| P9 | **Extract on evidence, not on fashion** | Split only for scaling, team, release-cadence, isolation or compliance reasons (see playbook §2). |

---

## 3. Repository layout (target)

```
BEFastAPI/
├── apps/                                  # COMPOSITION ROOTS — the only place that knows about >1 service
│   ├── monolith/                          # runs all enabled services in one process
│   │   ├── main.py                        # create_app(): mounts each enabled service
│   │   ├── wiring.py                      # binds consumer ports → providers (in-process adapters)
│   │   └── settings.py                    # ENABLED_SERVICES, shared infra URLs
│   ├── auth_api/main.py                   # runs ONE service standalone (≈10 lines each) — proves independence
│   ├── users_api/main.py
│   └── ...
│
├── services/                              # one folder == one future repo
│   ├── auth/
│   │   ├── pyproject.toml                 # package: auth-service   (private implementation)
│   │   ├── contracts/                     # package: auth-contracts (PUBLIC, tiny, separately installable)
│   │   │   ├── pyproject.toml
│   │   │   └── src/auth_contracts/
│   │   │       ├── api.py                 # Protocol(s) describing what others may ask of Auth
│   │   │       ├── dto.py                 # Pydantic DTOs crossing the boundary
│   │   │       ├── events.py              # versioned integration events (auth.user_registered.v1)
│   │   │       ├── errors.py              # contract-level exceptions / error codes
│   │   │       └── http_client.py         # HTTP implementation of api.py (used after extraction)
│   │   ├── src/auth_service/              # private implementation (see §4)
│   │   ├── migrations/                    # OWN Alembic env + version table, schema `auth`
│   │   ├── tests/
│   │   ├── Dockerfile                     # exists from day one, even if unused
│   │   └── README.md                      # owner, purpose, dependencies, runbook
│   ├── users/                             # same shape
│   ├── files/
│   ├── notifications/
│   └── _template/                         # scaffold copied by `tools/new_service.py`
│
├── libs/                                  # SHARED KERNEL — small, technical, business-agnostic
│   ├── platform_core/                     # config base, logging, error base, ids, clock, pagination, DB session factory
│   ├── platform_events/                   # EventBus port, in-process bus, transactional outbox, (future) broker adapters
│   ├── platform_http/                     # request-id/trace middleware, error handlers, httpx client base (timeouts, retries)
│   └── platform_security/                 # JWT verification (JWKS), Principal, permission helpers — NOT token issuing
│
├── tools/                                 # new_service.py, check_db_isolation.py, extraction_drill.py
├── docs/architecture/                     # this folder (+ ADR/)
├── docker-compose.yml                     # Postgres, Redis (later: broker)
├── pyproject.toml                         # uv workspace root: members = services/*, services/*/contracts, libs/*, apps/*
├── .importlinter                          # boundary contracts (see STANDARDS §8)
└── .github/workflows/                     # lint, types, architecture, tests-per-service, extraction-drill
```

Notes
- **`services/` is kept** (it already exists in the repo and matches the "User Service / File Service" vocabulary).
  Inside a service, code is organised by layer; across services, only `*_contracts` may be imported.
- **uv workspace** gives each service its own `pyproject.toml` and dependency list. A service's real dependencies are
  therefore *declared*, which is what makes copying it to another repo mechanical.
- `libs/*` are installed as normal packages. On first extraction they are published to a private index (or pinned by git tag);
  until then the workspace resolves them locally.

---

## 4. Anatomy of a service

```
services/<name>/src/<name>_service/
├── module.py            # ServiceModule: the single entry the composition root calls (router, startup, events, health)
├── settings.py          # <NAME>_-prefixed settings; never read by other services
├── api/                 # DRIVING ADAPTER: HTTP
│   ├── v1/              #   routers (thin), request/response schemas (HTTP-only models)
│   ├── internal/        #   /internal/v1 endpoints implementing contracts.api over HTTP (used after extraction)
│   └── deps.py          #   FastAPI Depends helpers (the only layer allowed to use Depends)
├── application/         # USE CASES: orchestration, transactions, authorization checks, event publishing
│   ├── services/        #   one class/function per use case or cohesive group
│   ├── ports.py         #   interfaces THIS service needs from outside (repos, other services, notifier, clock, ...)
│   ├── handlers/        #   subscribers to other services' events (idempotent)
│   └── jobs/            #   background/scheduled tasks owned by this service
├── domain/              # PURE: entities, value objects, enums, domain errors, policies. No FastAPI/SQLAlchemy/httpx.
├── infrastructure/      # DRIVEN ADAPTERS: implement application/ports.py
│   ├── db/              #   SQLAlchemy models, repositories, unit of work, outbox table
│   ├── clients/         #   adapters for OTHER services' contracts (in-process + http variants are selected in wiring)
│   └── providers/       #   3rd-party vendors (SMS, email, Google, S3 …) behind ports
└── contracts_impl.py    # implements <name>_contracts.api by delegating to application/ services (in-process provider)
```

### 4.1 Layer rules (dependency direction)

```
 api ───────► application ───────► domain
                  ▲                  ▲
                  │ implements       │
 infrastructure ──┴──────────────────┘          contracts_impl ► application
```

| Layer | May import | Must NOT import |
|---|---|---|
| `domain` | stdlib, `platform_core` primitives | FastAPI, SQLAlchemy, httpx, Redis, other services, `application`, `infrastructure`, `api` |
| `application` | `domain`, own `ports`, `platform_*`, **other services' `*_contracts`** (only via ports/adapters, see §6.1) | FastAPI, SQLAlchemy, concrete vendor SDKs, `api`, `infrastructure` |
| `infrastructure` | `application.ports`, `domain`, SQLAlchemy, SDKs, other services' `*_contracts` | `api`, other services' internals |
| `api` | `application`, `domain` types (read-only), `platform_http` | `infrastructure` (except via DI in `deps.py`), other services' internals |

Three different models, never conflated: **HTTP schema** (`api/`), **domain entity** (`domain/`), **ORM model** (`infrastructure/db/`),
plus the **contract DTO** (`*_contracts`) for the cross-service boundary. Mapping happens at each seam.

### 4.2 `module.py` — the single door

```python
# illustrative — not yet implemented
class ServiceModule(Protocol):
    name: str
    def settings(self) -> BaseSettings: ...
    def routers(self) -> list[APIRouter]: ...                 # public + internal routers (prefix /api/v1/<name>, /internal/v1/<name>)
    def register_event_handlers(self, bus: EventBus) -> None: ...
    def provide(self, container: Container) -> None: ...      # registers contracts_impl as provider of <name>_contracts.api
    async def on_startup(self) -> None: ...
    async def on_shutdown(self) -> None: ...
    def health(self) -> HealthReport: ...
```

The composition root loops over `ENABLED_SERVICES` and calls these. A service never mounts itself, never reaches for `app`.

---

## 5. Service map (initial)

| Service | Owns (source of truth) | Exposes (contracts) | Depends on (contracts) |
|---|---|---|---|
| **auth** | credentials, login identities (phone/email/google), sessions, refresh tokens, OTP challenges, lockout, **orgs, memberships, roles/permissions** | `AuthApi` (verify-principal helpers, get-membership, get-org), events `auth.user_registered.v1`, `auth.user_locked.v1`, `auth.org_member_added.v1`, … | `notifications` (send OTP/invite messages) |
| **users** | profile (display name, avatar ref, locale, timezone, preferences), user-facing settings | `UsersApi` (get profile(s) by id, batch) | `files` (avatar), reacts to `auth.user_registered.v1` |
| **files** | file metadata, storage keys, upload sessions, ACL links | `FilesApi` (create upload, get signed url, delete), events `files.file_uploaded.v1` | none |
| **notifications** | templates, delivery attempts, provider routing (SMS/email/push), user notification preferences | `NotificationsApi.send(message)`; events `notifications.delivery_failed.v1` | none (must not depend on auth/users; recipients are passed in) |

Dependency graph (must remain a DAG):

```
 auth ──► notifications
 users ─► files
 users ◄─(event: auth.user_registered.v1)─ auth      # event edge, not an import edge
```

Boundary calls worth recording now (so they don't get re-argued later):
- **Auth vs Users.** Auth keeps only what authentication/authorization needs (`id`, `status`, credentials, identities).
  *Profile* data lives in **users**. The Auth plan's `display_name / avatar_url / locale / timezone` columns move to Users (see §14).
- **OTP.** *Auth owns the OTP code* (generation, hash, expiry, attempts, static-OTP test mode) because it is a security decision.
  *Notifications owns delivery*. The vendor-neutral facade described in the Auth plan becomes the Notifications gateway;
  Auth talks to it through its own `OtpDelivery` port.
- **Identity everywhere.** Other services never call Auth to "check a token". They verify the JWT locally (JWKS) with
  `platform_security` and read the `Principal`. See §8.

---

## 6. Communication

### 6.1 Synchronous: consumer-owned port + swappable adapter

The consumer states **what it needs** in its own vocabulary; an adapter translates to the provider's contract.

```
users.application.ports.AvatarStore (Protocol)                 ← defined by Users, in Users' words
        ▲
users.infrastructure.clients.files_avatar_store.py             ← adapter (only place importing files_contracts)
        │ uses
files_contracts.api.FilesApi (Protocol)                        ← provider's public contract
        ▲                                   ▲
files_service.contracts_impl.FilesApiImpl   files_contracts.http_client.FilesHttpClient
   (in-process, used in monolith)              (HTTP, used after extraction)
```

- `apps/monolith/wiring.py` binds `FilesApi → FilesApiImpl`. After extraction, **only that line changes** to `FilesHttpClient(base_url=…)`.
- Contract methods are **coarse-grained and batchable** (`get_profiles(ids: list[UUID])`, not `get_profile` in a loop).
- Arguments/returns are contract DTOs (Pydantic, JSON-serialisable). Never ORM objects, sessions, `Request`, or domain entities.
- Failures are modelled: contract errors (`FilesUnavailable`, `FileNotFound`) exist in `*_contracts.errors`. The in-process impl raises the
  same exceptions the HTTP client would, so callers can't depend on same-process behaviour.
- Idempotency keys on commands that may be retried. Pagination on every list.
- **No sync chains:** a request handled by service A may call at most one hop (B). B must not call C to answer A. If you need that, use
  events/read-models or merge the services.

### 6.2 Asynchronous: versioned events + transactional outbox

- Events are **facts in past tense**, named `<service>.<noun>_<verb>.v<N>`, defined in `*_contracts.events`, Pydantic, minimal payload (IDs + the few
  fields consumers genuinely need, never full entities).
- A use case writes its data **and an outbox row in the same DB transaction**. A relay publishes outbox rows to the `EventBus`.
  - Today: `InProcessEventBus` dispatches after commit (same process, still via outbox → proves at-least-once/idempotent handlers early).
  - Later: swap relay target to a broker (Redis Streams / NATS / Kafka / SQS) — no producer or consumer business code changes.
- Handlers are **idempotent** (dedupe on `event_id`) and tolerate duplicates and reordering within reason.
- Event schema evolution: additive changes only within a version; breaking change ⇒ new `.v2` published in parallel until consumers move.
- Consumers keep their own **local read-model** of anything they need repeatedly (e.g. Users stores `user_id → status` if needed), instead of calling the owner on every request.

### 6.3 Choosing call vs event

| Situation | Use |
|---|---|
| "Give me data I need right now to answer this request" | sync call via port (batch, cached) |
| "Do this thing and tell me whether it worked" (command) | sync call via port, or async command with reply event if long-running |
| "Something happened that others may care about" | event |
| Another service needs a copy of data to work independently | event + local read-model |
| Cross-service transaction | **Not allowed.** Use saga/compensation via events, or redraw the boundary |

---

## 7. Data ownership

- One Postgres cluster today; **one schema per service** (`auth`, `users`, `files`, `notifications`) and **one DB role per service**
  with grants only on its schema (enforced in non-local environments; `tools/check_db_isolation.py` verifies).
- Each service has its **own Alembic environment**, own `alembic_version` table inside its schema, own migration history. Migrations run per service:
  `uv run --package auth-service alembic -c services/auth/migrations/alembic.ini upgrade head`.
- Each service has its **own `DATABASE_URL` setting** (`AUTH_DATABASE_URL`, …). They may point at the same cluster today.
  Extraction = `pg_dump -n auth | pg_restore` into a new database and change one URL.
- **No cross-schema foreign keys, joins, views or triggers.** Reference other services' entities by opaque ID (`user_id: UUID`) only. Integrity across
  services is eventual and handled by events (e.g. `auth.user_deleted.v1` → Users/Files clean up).
- **Redis**: key prefix per service (`auth:otp:*`, `files:*`); separate logical DB or ACL per service where possible. No shared keys.
- **Object storage**: prefix/bucket per owning service.

---

## 8. Identity, authentication and authorization across services

- Auth is the **only issuer** of tokens. It publishes `/.well-known/jwks.json` (see Auth plan §7).
- Every other service validates tokens **locally** using `platform_security` (JWKS cache, `iss`/`aud`/`exp`/`kid` checks) and receives a
  `Principal(user_id, session_id, org_id, roles, platform_roles, amr)`. This works identically in monolith and split modes.
- **Authorization**: each service decides what a principal may do **inside its own domain** (`files:upload` checked in Files). Role→permission
  definitions come from Auth's permission catalog; the *token* carries active org + role names; services evaluate with
  `platform_security.require_permission(...)`. Where a service needs fresh membership data it calls `AuthApi.get_membership(user_id, org_id)` via a port (cacheable).
- **Service-to-service identity** (post-extraction): short-lived service tokens (`client_credentials`-style, `sub=service:<name>`, `aud=<target>`)
  issued by Auth, or mTLS. Not needed while in-process; the `Principal` type already allows `kind="service"`.
- Internal HTTP routes (`/internal/v1/*`) require a service principal and are **never exposed through the public gateway**.

---

## 9. Composition root and deployment modes

`apps/*` is the only code allowed to import multiple services' `module.py`.

| Mode | How | When |
|---|---|---|
| **Monolith** | `apps/monolith`: `ENABLED_SERVICES=auth,users,files,notifications`; in-process adapters; in-process event bus | default, dev, early prod |
| **Single-service** | `apps/auth_api` (≈10 lines): mounts only auth; other services' ports bound to **fakes or HTTP clients** | CI "extraction drill"; first step of real extraction |
| **Split** | each service runs from its own repo/image; wiring uses `*HttpClient`s and a broker event bus | after extraction |
| **Hybrid** | monolith with `ENABLED_SERVICES` minus the extracted one; wiring binds its port to the HTTP client | during gradual migration — **both sides remain deployable** |

Public routes are namespaced `/api/v1/<service>/…` so a gateway (nginx, Kong, ALB, API Gateway) can route by prefix to a new origin without any client change.

---

## 10. Configuration and secrets

- Each service has a `Settings(BaseSettings)` with env prefix (`AUTH_`, `FILES_`). Shared infra (Redis URL, broker URL, log level) via `platform_core` base settings with their own prefix.
- A service must never import another service's settings or read its env vars.
- Secrets only from environment / secret manager. `.env.example` is committed; `.env` is not.
- Startup validation fails fast on unsafe combinations (e.g. static OTP in production).

---

## 11. Observability and operations

- Logs: structured JSON, always include `service`, `request_id`, `trace_id`, `user_id` (hash/ID only), no PII/secrets/OTP codes.
- Propagate `X-Request-ID` and W3C `traceparent` on every outbound call (HTTP clients do this by default) and as attributes on events.
- Metrics/traces tagged by `service` even in the monolith (`opentelemetry` instrumentation with a `service.name` per module) so dashboards survive extraction.
- Health: `/healthz` (liveness) and `/readyz` (readiness; aggregates each enabled module's `health()` + its DB/Redis checks).
- Background jobs belong to a service (`application/jobs`), registered through `module.py`, with queue/stream names prefixed by service.

---

## 12. API conventions

- Public: `/api/v1/<service>/<resource>`; version bumps are per service.
- Internal: `/internal/v1/<service>/…` mirrors `contracts.api` 1:1 (that's what `*HttpClient` calls).
- Uniform error body: `{ "error": { "code": "AUTH_ACCOUNT_LOCKED", "message": "...", "details": {}, "request_id": "..." } }`; codes are prefixed by service.
- Cursor pagination, ISO-8601 UTC timestamps, UUIDv7 (or ULID) identifiers, JSON snake_case.
- OpenAPI is generated per service (and merged in the monolith). The OpenAPI of `internal` routes is the provider side of the contract test.

---

## 13. Testing architecture

| Layer | What | Runs |
|---|---|---|
| Unit | domain + application with fakes (in-memory repos, fake clock, fake ports) | per service, no I/O |
| Integration | service + real Postgres/Redis (testcontainers) | per service |
| **Contract** | one shared suite per `*_contracts.api` run against **both** `…Impl` (in-process) and `…HttpClient` (against the real `/internal` routes) | per provider service |
| **Architecture** | import-linter contracts, DB-isolation check, "no cross-service ORM/FK" | repo-wide, every PR |
| **Extraction drill** | boot each `apps/<svc>_api` with *all other services' ports bound to fakes*; smoke-test its public API | nightly + on PRs touching `services/*` |
| End-to-end | monolith app, happy paths across services | main branch |

Each service's tests run in isolation: `uv run --package users-service pytest services/users`. If that needs another service's code, the boundary is wrong.

---

## 14. Reconciliation with the Auth plan (what changes)

The [Auth plan](../../services/auth/docs/PLAN.md) stays valid; it is re-homed into this structure:

| Auth plan item | New home / change |
|---|---|
| `services/auth/app/...` | `services/auth/src/auth_service/...` using the layer layout in §4 (`services` → `application/services`, `repositories`/`models` → `infrastructure/db`, `providers/sso` → `infrastructure/providers`) |
| `providers/notify` OTP facade (`NotificationGateway`, Static/Console/InMemory senders) | **Moves to the Notifications service.** Auth defines `OtpDelivery` port; adapter calls `notifications_contracts.NotificationsApi`. OTP code ownership + static-OTP mode stay in Auth |
| `users.display_name/avatar_url/locale/timezone` | **Moves to the Users service** (profile). Auth `users` table keeps `id`, `status`, credentials, lock fields, `token_version` |
| `audit_log` | Stays in Auth for auth events; other services keep their own audit tables (later: unify via events) |
| Orgs / memberships / RBAC | Stay in Auth (it issues the `org` claim and owns the permission catalog) — flagged as the most likely **future split** (`access` service) if org logic grows |
| JWKS + `platform_security` | JWKS endpoint in Auth; verification logic is the shared `libs/platform_security` |
| Phases 0–6 | Re-sequenced in [README §Roadmap](README.md#roadmap-no-code-yet) — Notifications v0 precedes Auth Phase 2 |

---

## 15. Risks and how the design contains them

| Risk | Mitigation |
|---|---|
| Boundaries drift ("just this once" import) | import-linter in CI; exceptions require an ADR with expiry |
| `libs/` becomes a dumping ground | libs are technical only; "rule of three" before promoting; CODEOWNERS on `libs/` |
| Over-engineering for a small team | One generator (`new_service.py`) produces the boilerplate; ceremony is paid once per service, not per feature |
| Contract package churn | Contracts are additive-only inside a version; consumer-driven contract tests |
| Distributed-monolith by sync chains | ≤ 1 hop rule, events + read-models, review checklist item |
| In-process calls hiding latency/failure | Contract impl raises the same errors as HTTP; chaos toggle in tests that injects latency/failures into in-process adapters |
| Premature extraction | Triggers and a readiness scorecard in the playbook |
