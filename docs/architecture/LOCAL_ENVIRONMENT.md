# Local Environment — Docker Compose

Status: **DRAFT for review** · Last updated: 2026-10-19

> **Goal:** `cp .env.example .env && docker compose up` brings up **every service, its database and migrations, Redis, the
> observability stack and dev tooling** — healthy, correlated and ready to use in a couple of minutes. A second command
> (`make up-split`, later) runs the same services as separate containers to rehearse extraction.

Related: [ARCHITECTURE §9](ARCHITECTURE.md) · [OBSERVABILITY](OBSERVABILITY.md) · [EXTRACTION_PLAYBOOK](EXTRACTION_PLAYBOOK.md)

---

## 1. Repository additions

```
BEFastAPI/
├── docker-compose.yml              # all services, with profiles (single source of truth)
├── compose.dev.yaml                # dev override: bind-mounts + uvicorn --reload (opt-in via `make dev`)
├── .env.example                    # every variable documented; COMPOSE_PROFILES defaults to "obs,tools"
├── Makefile                        # up / down / logs / migrate / test / lint / obs-smoke / reset
├── docker/
│   ├── Dockerfile                  # ONE multi-stage image for all apps (ARG APP=monolith|auth_api|…)
│   └── .dockerignore
├── deploy/
│   ├── postgres/init/              # 01-roles-schemas.sh: per-service schema + role (rule D-4), pg_stat_statements
│   ├── observability/
│   │   ├── otel-collector/config.yaml
│   │   ├── prometheus/prometheus.yml
│   │   ├── alertmanager/alertmanager.yml
│   │   ├── loki/loki.yaml
│   │   ├── tempo/tempo.yaml
│   │   ├── pyroscope/pyroscope.yaml          # optional profile
│   │   ├── grafana/provisioning/{datasources,dashboards,alerting}/
│   │   └── generated/              # assembled from services/*/observability by tools/sync_observability.py (gitignored)
│   └── keys/                       # dev-only key generation script (never committed keys)
└── services/<name>/observability/  # per-service dashboards, alert rules, SLOs, runbook (travel with the service)
```

---

## 2. Containers

### 2.1 Core (always on)
| Container | Image (pinned) | Purpose | Notes |
|---|---|---|---|
| `postgres` | `postgres:16` (+ `pg_stat_statements`) | single cluster, **schema + role per service** | init script creates `auth`, `users`, `files`, `notifications` schemas and roles; healthcheck `pg_isready` |
| `redis` | `redis:7` | OTP challenges, rate limits, caches, (later) streams | AOF off in dev; healthcheck `redis-cli ping` |
| `keygen` | app image (one-shot) | generates dev RS256 key pair into volume `dev-secrets` | prod uses a secret manager |
| `migrate-<svc>` | app image (one-shot, one per service) | runs **that service's own Alembic** to head | `depends_on: postgres healthy`; app containers wait for `service_completed_successfully` (rule D-3) |
| `app` (monolith) | app image, `APP=monolith` | all enabled services in one process (`ENABLED_SERVICES=auth,users,files,notifications`) | `:8000`; `/livez` `/readyz` healthchecks; non-root user; graceful SIGTERM |

### 2.2 Observability (`obs` profile — on by default via `.env`)
| Container | Purpose | Host port |
|---|---|---|
| `otel-collector` | OTLP in; redaction, sampling, spanmetrics/servicegraph; fan-out | 4317/4318 (local scripts) |
| `tempo` | traces | 3200 |
| `prometheus` | metrics + exemplars + rule evaluation (SLO burn-rate rules) | 9090 |
| `loki` | logs (OTLP ingest) | 3100 |
| `alertmanager` | alert routing | 9093 |
| `grafana` | dashboards, explore, correlation (all provisioned as code) | **3000** |
| `postgres-exporter`, `redis-exporter` | DB/cache metrics | — |
| `blackbox-exporter` | probes `/readyz` over the network path | — |
| `pyroscope` *(optional profile `profiling`)* | continuous profiling | 4040 |

### 2.3 Developer tooling (`tools` profile — on by default via `.env`)
| Container | Purpose | Host port |
|---|---|---|
| `mailpit` | SMTP sink + UI for email OTP/invites in dev | 8025 (UI), 1025 (SMTP) |
| `adminer` | quick DB browsing | 8080 |
| `minio` *(added with Files service)* | S3-compatible storage for Files | 9000/9001 |

### 2.4 Split mode (`split` profile — enabled once ≥2 services have HTTP clients and the broker bus)
Per-service containers from the **same image**: `auth-api` (`APP=auth_api`), `users-api`, `files-api`, `notifications-api`, plus a
`broker` (Redis Streams to start) and a tiny `gateway` (Caddy/nginx) routing `/api/v1/<service>/**` by prefix — this is the extraction rehearsal environment
(Playbook step 5–6) and the proof that wiring is the only seam. Not built in Phase A; the compose file reserves the profile and naming.

---

## 3. Networks, volumes, configuration

- **Networks:** `edge` (host-exposed: app, gateway, grafana), `backend` (app ↔ postgres/redis/broker), `obs` (app/collector/backends). The DB and Redis are not published to the host unless `EXPOSE_DB=true` (override file).
- **Volumes (named):** `pg-data`, `redis-data`, `grafana-data`, `prometheus-data`, `loki-data`, `tempo-data`, `dev-secrets`. `make reset` removes them.
- **Configuration:** only environment variables, from `.env` (gitignored) with `.env.example` as the reference. Per-service prefixes (`AUTH_`, `USERS_`, …); shared infra via `PLATFORM_`/`OTEL_*`. No secrets in the compose file.
- **Pinned versions:** no `latest` tags; Renovate/Dependabot keeps image digests current.
- **Resource limits:** modest defaults (`mem_limit`) so the full stack fits a 16 GB laptop; documented in `.env` (`OBS_LITE=true` skips Tempo/Loki/Pyroscope heavy parts if needed).

### 3.1 Key environment variables (excerpt)
```
COMPOSE_PROFILES=obs,tools           # `docker compose up` starts app + obs + tools
APP_VERSION=dev
ENV=local
ENABLED_SERVICES=auth,users,files,notifications

PLATFORM_REDIS_URL=redis://redis:6379/0
AUTH_DATABASE_URL=postgresql+asyncpg://auth:auth@postgres:5432/befastapi?options=-csearch_path%3Dauth
USERS_DATABASE_URL=…            FILES_DATABASE_URL=…            NOTIFICATIONS_DATABASE_URL=…

AUTH_OTP_MODE=static             # local only; app refuses to boot with static OTP when ENV=production
AUTH_OTP_STATIC_CODE=123456
NOTIFICATIONS_SMTP_URL=smtp://mailpit:1025

OTEL_SERVICE_NAME=befastapi-monolith
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_RESOURCE_ATTRIBUTES=service.namespace=befastapi,deployment.environment.name=local
OTEL_TRACES_SAMPLER=parentbased_always_on
```

---

## 4. Image and runtime standards

- **One Dockerfile**, multi-stage: `builder` (uv, `uv sync --frozen --package <app>`), `runtime` (python:3.12-slim, non-root UID, `PYTHONUNBUFFERED`, no build tools). The app to run is a build `ARG`/env (`APP=monolith`), so extracted services reuse the pattern (each service also keeps its own `Dockerfile` that copies only itself + pinned libs — see Playbook step 2).
- `HEALTHCHECK` → `/readyz`; `STOPSIGNAL SIGTERM`; Uvicorn/Gunicorn with graceful shutdown (drain, flush OTel exporters, close pools).
- Container labels: `org.opencontainers.image.version/revision`, `app.service`.
- Logs go to stdout as JSON (Docker `json-file` with rotation); OTLP logs also go to Loki.
- Startup ordering uses health conditions, never `sleep`: `postgres(healthy) → keygen/migrate-*(completed) → app(healthy) → ready`.

---

## 5. Developer workflow (Makefile)

| Command | Does |
|---|---|
| `make up` | `docker compose up -d --build` with profiles from `.env` (app + obs + tools) |
| `make dev` | same + `compose.dev.yaml`: bind-mount source, `uvicorn --reload`, debug ports |
| `make down` / `make reset` | stop / stop and delete volumes |
| `make logs [s=app]` | tail logs |
| `make migrate [s=auth]` | run one/all service migrations on demand |
| `make test [s=users]` | run a service's tests **in isolation** (`uv run --package …`) |
| `make lint` | ruff, mypy, import-linter, DB-isolation, service-map, rules/dashboards lint |
| `make obs-smoke` | scripted request → verifies trace in Tempo, logs in Loki, metric in Prometheus, correlation links |
| `make drill s=auth` | extraction drill: boot `auth_api` alone with fakes, migrate empty DB, smoke test |
| `make up-split` *(later)* | split profile: separate containers + broker + gateway |

URLs after `make up`: API `http://localhost:8000/docs` · Grafana `http://localhost:3000` · Prometheus `:9090` · Alertmanager `:9093` · Mailpit `:8025` · Adminer `:8080`.

---

## 6. Acceptance criteria for the local environment

1. Fresh clone → `cp .env.example .env && docker compose up` → all containers healthy in **≤ 3 min** (cold) / ≤ 45 s (warm), no manual steps.
2. `GET /readyz` lists every enabled module as `ok`; adding a service via `tools/new_service.py` makes it appear without editing compose (generator updates `ENABLED_SERVICES`, `postgres/init`, `migrate-<svc>` entry).
3. A request to any endpoint yields, in Grafana within seconds: a trace (with `app.service` + use-case spans), correlated logs (same `trace_id`), RED metrics with exemplars.
4. Killing Postgres, Redis, or the Collector degrades gracefully: readiness fails/recovers as expected; the app keeps serving what it can and drops telemetry without errors.
5. `make reset && make up` is reproducible (idempotent init scripts, migrations from empty).
6. `make test s=<svc>` passes with **only that service** installed — compose is not required for unit tests; integration tests use testcontainers (or the compose Postgres via `TEST_DATABASE_URL`).
7. No secrets or real credentials are committed; dev keys are generated at first start.
