# Architecture Documentation — BEFastAPI

Status: **ACCEPTED — decisions A1–A12 confirmed 2026-10-19** · Last updated: 2026-10-19

A modular FastAPI monolith where **each service (Auth, Users, Files, Notifications, …) is built to be lifted out into its own
repo and deployed separately with ≈ 1–2 days of mechanical work.**

| Doc | Read it for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Principles, repo layout, anatomy of a service, service map, communication (calls + events), data ownership, identity, deployment modes, testing architecture |
| [STANDARDS.md](STANDARDS.md) | Numbered rules (B/L/D/C/X/S/T), 26 named anti-patterns with detection, CI enforcement (import-linter etc.), exceptions process, PR checklist |
| [EXTRACTION_PLAYBOOK.md](EXTRACTION_PLAYBOOK.md) | When to extract, readiness scorecard, step-by-step cutover, hybrid mode, rollback, time budget, quarterly drill |
| [Auth plan](../../services/auth/docs/PLAN.md) | Detailed Auth + RBAC design (re-homed into this structure; see ARCHITECTURE §14) |

## The design in six lines

1. `services/<name>/` is one future repo: own `pyproject.toml`, own DB schema + Alembic, own settings, own Dockerfile.
2. Each service has a tiny public **`<name>_contracts`** package (DTOs, Protocols, events, errors, HTTP client). Everything else is private.
3. Consumers define a **port** in their own words; an adapter binds it to the provider's contract — in-process today, HTTP after extraction.
4. State changes publish **versioned events via a transactional outbox**; in-process bus today, broker later.
5. **`apps/`** is the only place that wires services together; extraction = change one binding + move one schema.
6. **CI enforces it** (import-linter, DB-isolation check, per-service test runs, extraction drill).

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

## Roadmap (no code yet)

Order matters: structure and guardrails first, then services from leaf to root of the dependency graph.

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **A. Foundation** | uv workspace, `libs/platform_{core,events,http,security}` skeletons, `apps/monolith` + health, docker-compose (Postgres, Redis), CI (ruff, mypy, import-linter, per-service test matrix), `tools/new_service.py`, `.importlinter` generator, PR template, CODEOWNERS | `new_service.py demo` produces a service that passes all CI checks and the extraction drill |
| **B. Notifications v0** | `notifications` service: gateway/facade, Static/Console/InMemory senders, `NotificationsApi.send`, delivery log | contract tests pass on Impl + HttpClient; no dependency on other services |
| **C. Auth** | Auth plan phases 0–6 mapped into the layer layout; `OtpDelivery` port → Notifications; JWKS; org-scoped RBAC | Auth runs standalone via `apps/auth_api`; extraction drill green |
| **D. Users** | profile service reacting to `auth.user_registered.v1`; `UsersApi.get_profiles(ids)` | no import of Auth internals; event handler idempotency tests |
| **E. Files** | metadata, upload sessions, signed URLs, storage provider port (S3/local) | avatar flow Users→Files through a port |
| **F. First drill** | run the extraction drill on Notifications in staging | measured against the playbook time budget; findings folded into STANDARDS |

Auth Phases 0–6 re-sequence: scaffolding is covered by Phase A; **Auth Phase 2 (OTP + facade) is split** — the OTP code logic stays in Auth, the delivery facade is built in Phase B.

## Glossary

- **Service**: a business capability with its own code, data, contract, and config. Today a folder; tomorrow possibly a repo/deployment.
- **Contract**: the public, versioned surface of a service (`<name>_contracts`): DTOs, `Protocol`s, events, errors, HTTP client.
- **Port / adapter**: a consumer-owned interface for what it needs / the implementation that binds it to a provider or vendor.
- **Composition root**: `apps/*` — the only place where services are wired together.
- **Outbox**: a table written in the same transaction as a state change, relayed to the event bus afterwards.
- **Principal**: the authenticated caller (user or service) decoded from a verified JWT.
- **Extraction drill**: automated check that a service boots, migrates, and passes smoke tests alone.
