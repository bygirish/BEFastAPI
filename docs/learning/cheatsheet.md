# Cheat-sheet

## Daily commands
```bash
make install            # uv sync --all-packages  (create/refresh .venv)
make lint               # ruff + format check + generated-files check + architecture contracts
make typecheck          # mypy --strict on every package
make test               # all tests
make test-service s=notes-service p=services/notes/service   # one service, only its own deps installed
make format             # auto-fix style
make new-service name=notes     # scaffold a service
make scaffold-check     # prove the scaffold still produces a green service
uv run uvicorn --factory monolith_app.main:create_app --reload   # run the monolith
```

## Where does this code go?
| I am writing… | Put it in… | Allowed to import |
|---|---|---|
| A business rule / pure error | `domain/` | stdlib, `platform_core` only |
| "Do X when the user asks" | `application/services/` (a use case) | `domain`, `ports`, platform libs |
| An interface to the outside (repo, other service, vendor) | `application/ports.py` | `domain`, platform libs |
| SQL, ORM tables, unit of work | `infrastructure/db/` | `application.ports`, `domain`, SQLAlchemy |
| Calling **another service** | `infrastructure/clients/` (adapter) | **only** `<other>_contracts` |
| A vendor SDK (SMS, e-mail, storage) | `infrastructure/providers/` | the SDK + `application.ports` |
| An HTTP route | `api/v1/router.py` (thin!) | `application`, `api/deps.py` |
| HTTP request/response shapes | `api/v1/schemas.py` | pydantic |
| `Depends(...)` helpers | `api/deps.py` | FastAPI, `application` |
| What other services may use | `<name>_contracts` (separate package) | pydantic, `platform_core/events/http` |
| Wiring services together | `apps/*` only | anything |

## The rules in one breath
1. Import another service **only** through its `*_contracts` (**B-1**).
2. `domain` / `application` never import FastAPI, SQLAlchemy, httpx, redis (**L-2, L-3**).
3. Routers are thin: parse → one use case → return (**L-4**).
4. One schema + one Alembic per service; no cross-service SQL/FK (**D-1…D-3**).
5. Event + data in one transaction via the outbox (**D-5**); handlers are idempotent (**C-7**).
6. Treat every cross-service call as remote: DTOs only, batch it, handle failure, ≤ 1 hop (**C-1…C-5**).
7. Identity comes from the verified token, never from the request body (**X-2**).
8. Log once, structured, no secrets; metric labels are closed sets (**O-2…O-5**).
9. Every cross-boundary change is additive and has a contract test (**C-10, T-3**).

Full list with explanations: [STANDARDS](../architecture/STANDARDS.md).

## URL conventions
| Kind | Pattern | Who calls it |
|---|---|---|
| Public API | `/api/v1/<service>/…` | clients / gateway |
| Internal API | `/internal/v1/<service>/…` | other services only (service token) |
| Health | `/livez` `/readyz` `/startupz` | orchestrator / load balancer |

## Error body (always this shape)
```json
{"error": {"code": "NOT_FOUND", "message": "Not Found", "details": {}, "request_id": "01a152a4-…"}}
```
`code` is service-prefixed for service errors (`AUTH_ACCOUNT_LOCKED`).

## Naming
| Thing | Convention | Example |
|---|---|---|
| Service name | `[a-z][a-z0-9]*` (no underscores) | `notifications` |
| Event | `<service>.<noun>_<verb>.v<N>` (past tense) | `auth.user_registered.v1` |
| Env vars | `<SERVICE>_…` | `AUTH_DATABASE_URL` |
| Metric | `<service>.<noun>[.<verb>]` | `auth.login.attempts` |
| Use case | a verb phrase, class name | `RegisterUser` |
| Port | a noun | `AvatarStore`, `Clock` |

## Reading a JSON log line
`event` (what happened, constant) · `severity` · `request_id` · `trace_id`/`span_id` (jump to the trace) · `app.service`
(which logical service) · everything else is data about the event. Search by `request_id` to follow one request.
