# Observability Standard

Status: **DRAFT for review** · Last updated: 2026-10-19 · Applies to every service, lib and app

> **Goal:** from any alert, dashboard panel, error message or user complaint, an engineer can reach the exact trace, the exact
> log lines and the relevant metrics in **≤ 3 clicks** — in the monolith today and across processes after extraction —
> **without any per-service glue code.**

Related: [ARCHITECTURE §11](ARCHITECTURE.md) · [STANDARDS §5 (O-rules), AP-27…AP-33](STANDARDS.md) · [LOCAL_ENVIRONMENT](LOCAL_ENVIRONMENT.md)

---

## 1. Principles

| # | Principle | Consequence |
|---|---|---|
| O-P1 | **OpenTelemetry everywhere** | One vendor-neutral API/SDK/wire protocol (OTLP) for traces, metrics, logs. Backends are swappable (Grafana stack locally; Datadog/Honeycomb/Cloud later) by changing the Collector config only. |
| O-P2 | **The three signals are correlated by construction** | Every log line carries `trace_id`/`span_id`; metrics carry exemplars linking to traces; traces link to logs and metrics in Grafana. |
| O-P3 | **Instrument once, in the platform** | Services get HTTP/DB/Redis/HTTP-client/event instrumentation for free from `libs/platform_observability`. Service code adds only business spans/metrics. |
| O-P4 | **Observability assets travel with the service** | Dashboards, alert rules, SLOs and runbooks live in `services/<name>/observability/`, so extraction moves them too. |
| O-P5 | **Alert on symptoms (SLO burn), debug with causes** | Pages come from user-visible SLO burn rates, not CPU or log counts. |
| O-P6 | **Low cardinality, no PII** | Metric labels are enumerations; telemetry never contains secrets, OTPs, tokens, passwords or raw PII. Enforced by processors + tests. |
| O-P7 | **Same in monolith and split** | Every signal carries `app.service` (the logical service) in addition to the OTel `service.name` (the process), so dashboards survive extraction unchanged. |
| O-P8 | **Observability must not break the app** | Exporters are async/batched/non-blocking; collector down ⇒ drop and count, never fail a request. |

---

## 2. Telemetry pipeline

```
 ┌──────────────── monolith process (or any service process) ────────────────┐
 │  FastAPI ─ SQLAlchemy ─ redis ─ httpx ─ outbox/event bus ─ use cases        │
 │      └─ platform_observability: OTel SDK (traces, metrics, logs) ───────────┼──► OTLP (gRPC 4317)
 │      └─ stdout: JSON logs (12-factor; `docker logs` still works)            │
 └─────────────────────────────────────────────────────────────────────────────┘
                                                                                 │
                                                         ┌───────────────────────▼──────────────────────┐
                                                         │ OpenTelemetry Collector (contrib)            │
                                                         │  memory_limiter → resource detection →       │
                                                         │  attribute redaction (safety net) →          │
                                                         │  tail sampling (prod) → batch                │
                                                         │  spanmetrics + servicegraph connectors       │
                                                         └───┬───────────────┬───────────────┬──────────┘
                                                             │ traces        │ metrics       │ logs
                                                          Tempo        Prometheus          Loki
                                                             └─────────┬─────┴───────────────┘
                                                                    Grafana  ── Alertmanager (rules in Prometheus)
 Infra exporters (postgres, redis, collector self-metrics, blackbox probes) ──► Prometheus
 Optional: Pyroscope (continuous profiling), Sentry/GlitchTip (error grouping via DSN env)
```

- Apps never talk to a backend directly — only to the Collector (OTLP). Swapping a backend never touches application code.
- Defaults (local): Tempo, Prometheus (OTLP/remote-write with exemplars), Loki (OTLP ingest), Grafana, Alertmanager.
- Retention (local defaults): traces 3 d, logs 7 d, metrics 15 d. Production values come from infra policy, not code.

---

## 3. Resource attributes (identity of telemetry)

Set once by `platform_observability.setup()` from env + settings. Required on **every** signal:

| Attribute | Example | Notes |
|---|---|---|
| `service.name` | `befastapi-monolith` / `auth-service` | the *process* (OTel standard) |
| `service.namespace` | `befastapi` | |
| `service.version` | `1.4.2+gitsha` | build arg → env `APP_VERSION` |
| `service.instance.id` | pod/container id | |
| `deployment.environment.name` | `local` / `staging` / `prod` | |
| **`app.service`** | `auth`, `users`, `files`, `notifications` | the *logical* service owning the code path; set by middleware/context from the router/use-case owner. Used for dashboards, SLOs, alerts |
| `app.module_mode` | `monolith` / `standalone` | helps compare modes |

Mechanics: a `ServiceModule` registers its `app.service` name; `platform_observability` wraps its router/handlers/jobs so a context variable
`current_app_service` is set, and a span/metric/log processor stamps it. Application code never sets it manually.

---

## 4. Logging standard

**Format:** one JSON object per line to **stdout** (and via OTel log bridge → Collector → Loki). Library: `structlog` configured on top of stdlib logging so third-party logs are captured too.

Required fields (OTel naming where one exists):

```json
{
  "timestamp": "2026-10-19T10:15:30.123Z", "severity": "INFO", "event": "login_succeeded",
  "service.name": "befastapi-monolith", "app.service": "auth", "deployment.environment.name": "local", "service.version": "…",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "00f067aa0ba902b7", "request_id": "…",
  "enduser.id": "usr_01J…", "org.id": "org_01J…",
  "http.request.method": "POST", "http.route": "/api/v1/auth/login/password", "http.response.status_code": 200,
  "login.method": "password", "duration_ms": 41
}
```

Rules
- `event` is a **constant snake_case string**; variable data goes in fields — never in an f-string message (keeps logs queryable and aggregatable).
- Levels: `ERROR` = needs human attention / request failed unexpectedly; `WARNING` = handled anomaly (retry, degraded, rate-limit hit); `INFO` = business-significant lifecycle events (not per-query noise); `DEBUG` = off in prod. 4xx caused by clients are `INFO`/`WARNING`, not `ERROR`.
- **Log once, at the boundary.** Don't log-and-rethrow in every layer. Domain/application raise typed errors; the HTTP error handler / job runner / event-handler wrapper logs them once with full context and `exception.type/message/stacktrace`.
- **Never log:** passwords, OTP codes, tokens (access/refresh/reset/signup), `Authorization`/`Cookie` headers, full phone/email (use masked `a***@x.com`, `+91*****1234` or the user ID), request bodies by default.
- **Redaction is automatic:** a structlog processor drops/masks a denylist of keys (`password`, `otp`, `code`, `token`, `authorization`, `secret`, `api_key`, …) and a regex pass masks JWT-shaped and card-shaped strings. The Collector repeats a safety-net redaction. A test asserts this (T-8).
- **Audit logs** (security-relevant actions: login, lock, role change, token reuse) are a *separate stream*: `event.category="audit"`, stored in the service's audit table **and** emitted as logs; retention and access differ from operational logs.
- `print()` and bare `logging.getLogger().info("f-string")` are banned (ruff rule `T20`, custom check).
- Sampling/noise control: health/readiness/metrics endpoints are not logged at INFO; repeated identical errors are rate-limited in the logger.

---

## 5. Metrics standard

**API:** OpenTelemetry Metrics API (`opentelemetry-api` allowed in `api/`, `application/`, `infrastructure/`; **not in `domain/`**; SDK/exporters only inside `platform_observability`).

### 5.1 Automatic (from the platform)
| Area | Metrics (OTel semantic conventions) |
|---|---|
| HTTP server (RED) | `http.server.request.duration` (histogram, s), `http.server.active_requests`; attributes `http.request.method`, `http.route` (**template**, never raw path), `http.response.status_code`, `app.service` |
| HTTP client | `http.client.request.duration` per target service/vendor |
| DB | `db.client.operation.duration`, pool `db.client.connection.count/usage/wait_time`; slow-query counter (> 200 ms) |
| Redis | `db.client.operation.duration` (system=redis) |
| Events / outbox | `events.outbox.pending` (gauge), `events.publish.lag` (s), `events.handler.duration`, `events.handler.failures` (by handler, event type), `events.dead_lettered` |
| Jobs | `jobs.duration`, `jobs.failures`, `jobs.last_success_timestamp` |
| Runtime | process CPU/memory, GC, event-loop lag, thread/FD counts |
| Rate limiting | `ratelimit.rejected` by policy |

### 5.2 Business metrics (declared by each service)
Declared once in `services/<name>/src/<name>_service/application/telemetry.py` (a small module of instrument handles) and documented in `services/<name>/observability/README.md`. Examples for Auth:

| Metric | Type | Attributes (closed sets) |
|---|---|---|
| `auth.login.attempts` | counter | `method` (password/otp_sms/otp_email/google), `outcome` (success/invalid_credentials/locked/rate_limited/error) |
| `auth.otp.sent` / `auth.otp.verified` | counter | `channel`, `purpose`, `outcome` |
| `auth.account.locked` | counter | `reason` |
| `auth.token.refresh` | counter | `outcome` (ok/reuse_detected/expired) |
| `auth.sessions.active` | observable gauge | — |
| `notifications.delivery` | counter + `notifications.delivery.duration` | `channel`, `provider`, `outcome` |

### 5.3 Rules
- Names: dotted lower-case `<service>.<noun>[.<verb>]`, base units in the `unit` field (`s`, `By`, `1`), counters monotonic; histograms use explicit boundaries suited to latency (`5ms … 10s`) defined once in the platform.
- **Cardinality budget:** attribute values come from closed enumerations. Forbidden as attributes: user/org/session IDs, emails, phones, IPs, raw URLs, error messages, free text. (IDs belong in traces/logs.) A test fails if an unknown attribute key is used on a registered instrument (allow-list per instrument).
- **Exemplars** enabled on latency histograms so a slow bucket links to a trace.
- Every new endpoint/use case/handler inherits RED metrics automatically; PRs only add business metrics.

---

## 6. Tracing standard

- **Context propagation:** W3C `traceparent` + `tracestate` + `baggage` (restricted to `app.caller`, never PII). Inbound HTTP extracts; outbound `httpx` injects. In-process calls simply continue the current span (so monolith traces look the same as split traces, with the same span names).
- **Auto-instrumentation** (via `platform_observability`): FastAPI's *built-in* OpenTelemetry (server + dependency/endpoint/serialization spans; its own metrics and logs are switched off so RED metrics come only from our middleware and errors are logged once, redacted), SQLAlchemy (+asyncpg), Redis, httpx, logging correlation.
- **Manual spans (required):**
  - one span per **use case** — `auth.RegisterUser`, kind=INTERNAL, attribute `app.service`;
  - one span per **contract call** at the adapter seam — `files_contracts.FilesApi.get_signed_url` (kind=CLIENT in both in-process and HTTP impls; the HTTP impl's span nests the httpx span). This is what makes the call graph visible in the monolith and identical after extraction;
  - **events:** outbox rows store the producer's `traceparent`; the relay creates a PRODUCER span and the handler a CONSUMER span with a **span link** to the producer (async work is linked, not parented);
  - jobs: root span per run (`jobs.<service>.<name>`).
- **Span naming:** `<METHOD> <route template>` for HTTP, `<service>.<UseCase>` for use cases, `<verb> <table>` for DB (auto). Never put IDs or query values in span names.
- **Attributes:** semantic-convention names first; domain attributes under `app.*` / `<service>.*`; IDs allowed on spans (not metrics) but PII is not (masked identifiers only). Record exceptions with `span.record_exception` and set status ERROR only for server-side failures (not for 4xx).
- **Sampling:** local/dev 100 %. Production: head sampling at 100 % in the app, **tail sampling in the Collector** — keep 100 % of errors and of traces slower than the latency SLO, plus a 5–10 % baseline (policy file in `deploy/observability/otel-collector/`). Sampling decisions never live in application code.
- **Span-derived metrics:** Collector `spanmetrics` + `servicegraph` connectors produce RED per `app.service` and a service dependency graph — useful even in the monolith (shows logical call edges and flags rule C-5 violations: depth > 1).

---

## 7. Health, readiness, and probes

| Endpoint | Meaning | Checks |
|---|---|---|
| `/livez` | process is alive | event loop responsive; no deps |
| `/readyz` | can serve traffic | for each *enabled* module: DB reachable + migrations at head, Redis reachable, required config present; returns per-module status JSON |
| `/startupz` | finished boot | migrations/keys loaded (for slow starts) |

- Excluded from tracing/logging noise, included in metrics with `http.route` label.
- Prometheus **blackbox** probes hit `/readyz` through the real network path; probe success feeds the availability SLO's *external* view.

---

## 8. SLOs, dashboards and alerts (assets live in each service)

```
services/<name>/observability/
├── slo.yaml            # SLIs/SLOs for this service (declarative)
├── alerts.rules.yaml   # generated from slo.yaml + hand-written cause alerts
├── dashboards/         # Grafana JSON (provisioned), generated from a template then hand-tuned
├── runbook.md          # one section per alert, linked from alert annotations (runbook_url)
└── README.md           # metrics catalog, log events catalog, span names
```

### 8.1 SLOs (defaults; per-service overrides in `slo.yaml`)
| SLI | Definition | Default objective |
|---|---|---|
| Availability | non-5xx / total on the service's **public** routes (4xx excluded) | 99.9 % / 30 d |
| Latency | % requests faster than threshold (default 500 ms; Auth login 800 ms) | 99 % / 30 d |
| Event freshness | % events handled within 30 s of publish | 99 % / 30 d |
| Delivery (Notifications) | % OTP deliveries accepted by a provider within 10 s | 99.5 % / 30 d |

### 8.2 Alerting
- **Multi-window multi-burn-rate** alerts (Google SRE workbook) generated by `tools/gen_slo_rules.py` from `slo.yaml`:
  page at 14.4× (1 h & 5 m) and 6× (6 h & 30 m); ticket at 1× (3 d & 6 h).
- Cause-based alerts only where no SLI exists yet: outbox backlog age, DB pool saturation, certificate/secret expiry, disk, collector dropping data.
- Every alert has: `severity`, `app_service`, `summary`, `description`, `runbook_url`, `dashboard_url`. Alerts without a runbook section fail CI.
- Routing via Alertmanager: `page` → on-call receiver; `ticket` → issue tracker; local default = null receiver + Grafana alert list.
- Alerts, SLOs and dashboards are **code-reviewed** and validated in CI (`promtool check rules`, Grafana JSON schema, link check for runbooks).

### 8.3 Standard dashboards
1. **Overview** — SLO status/burn per service, request rate, error ratio, latency heatmap, top slow routes, active alerts.
2. **Service (templated by `app_service`)** — RED, business metrics, dependency calls (from servicegraph), outbox/event lag, jobs, recent error logs panel, exemplar-enabled latency panel.
3. **Database** — Postgres (via `postgres_exporter` + `pg_stat_statements`): connections, locks, slow queries, per-schema size/activity.
4. **Redis**, **Collector/Pipeline health** (dropped spans, queue size), **Runtime** (CPU, memory, GC, event-loop lag).
5. **Security/Audit (Auth)** — login outcomes, lockouts, OTP volumes by country/channel (SMS-pumping detection), refresh-token reuse events.

### 8.4 Correlation set-up (Grafana provisioning)
- Metrics → Traces via exemplars (`trace_id`); Traces → Logs by `trace_id` (Loki derived field); Logs → Traces via `trace_id` link; Traces → Metrics (RED for the span's route); Alerts → dashboard/runbook links.
- Data-source UIDs and links are provisioned as code, so a fresh `docker compose up` already has full correlation.

---

## 9. Safeguards and governance

- **PII/secret hygiene:** redaction processors (app + Collector); unit tests feed sample secrets through logger/span/metric APIs and assert absence (T-8); CI `gitleaks` for repo secrets.
- **Cardinality guard:** instrument allow-lists (§5.3); Prometheus `series_limit` / Collector `filter` drop on violation; dashboard panel for top series.
- **Cost/volume guard:** log level by env, sampling policy in Collector, drop `/livez`/`/metrics` spans and logs, size limits on attribute values (e.g. 1 KB).
- **Exporter failure behaviour:** bounded queues, drop-oldest, a counter `otel.dropped` and an alert if the Collector rejects/drops > 1 %.
- **Config via standard env vars** (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_TRACES_SAMPLER`, `OTEL_RESOURCE_ATTRIBUTES`, `OTEL_SDK_DISABLED`) so ops can change behaviour without code changes. `OTEL_SDK_DISABLED=true` makes everything a no-op (unit tests, scripts).
- **Time/clock:** all timestamps UTC; durations measured with monotonic clocks.
- **Time-to-detect budget:** an injected failure in the extraction drill / chaos test must trigger the matching alert in < 5 min (see §10).

---

## 10. Verifying observability itself

| Test | What it proves | Where |
|---|---|---|
| Telemetry contract test | A request through each service produces: a server span with `app.service`, a use-case span, DB span, log lines containing the same `trace_id`, and RED metrics with exemplars | `libs/platform_observability/testing` (in-memory OTel exporters), run by each service |
| Redaction test (T-8) | Secrets/OTPs/PII never reach logs/spans/metrics | per service + libs |
| Cardinality test | Instrument attributes ⊆ allow-list | per service |
| Pipeline smoke test | `docker compose up` then a scripted request → trace visible in Tempo, logs in Loki, metric in Prometheus, links resolve | `tools/obs_smoke.py` (CI nightly) |
| Alert fire-drill | Inject errors/latency (toggle) → burn-rate alert fires within budget | staging; quarterly with the extraction drill |
| Rules lint | `promtool check rules`, dashboard JSON validity, runbook anchors exist | CI on every PR |

---

## 11. Library: `libs/platform_observability`

```
platform_observability/
├── setup.py          # setup(settings, app_service_registry): configures SDK providers, exporters, resource, propagators
├── logging.py        # structlog + stdlib integration, JSON renderer, redaction processor, trace/request context injection
├── metrics.py        # histogram boundaries, instrument factory with attribute allow-lists
├── tracing.py        # tracer helper, @traced_use_case, span helpers for contract adapters/outbox/jobs
├── context.py        # contextvars: request_id, app_service, principal summary
├── middleware.py     # ASGI: request id, access log, app.service stamping, error → span/log recording
├── health.py         # /livez /readyz /startupz builders aggregating module.health()
├── redaction.py      # key denylist + regex maskers (shared by logs/spans)
└── testing.py        # in-memory exporters + assertion helpers
```

- Depends only on OTel packages and `platform_core`; **never** on services (B-3).
- Provides **no-op fallbacks**: if `OTEL_SDK_DISABLED=true`, nothing is exported but logs still go to stdout.

---

## 12. Extraction impact

- Because dashboards/alerts/SLOs/runbooks live in the service folder, `git filter-repo --subdirectory-filter` carries them along; the new repo's CI runs the same rule/dashboard lint.
- `app.service` already exists on all signals; after extraction `service.name` changes from `befastapi-monolith` to `auth-service`, and dashboards that filter by `app_service` need **no edits**.
- Traces gain real network hops where in-process contract spans already existed — same span names, so trace comparisons before/after cutover are direct.
- The Collector/Grafana stack is infra, not service code; it stays shared.
