# KT · 04 — Architecture Diagrams

**Goal:** the whole system in pictures, from "who uses it" down to "which library imports which" — the diagrams you'd draw on a whiteboard to explain the project in 15 minutes.
**How to read:** go top-down (context → containers → components → behaviour). Each diagram answers one question. GitHub renders Mermaid; if you can't see them, paste the code into <https://mermaid.live>.

---

## 1. System context — who and what touches us?

```mermaid
flowchart LR
  client["Client apps<br/>(web, mobile, other backends)"] -->|"HTTPS /api/v1/…"| platform
  op["Developers & operators"] -->|"Grafana, Prometheus, docs"| platform
  subgraph platform["BEFastAPI platform (one deployable today)"]
    svc["Auth · Users · Files · Notifications …"]
  end
  platform -.->|"Phase B/C: SMS, e-mail, Google sign-in"| vendors["External vendors"]
  platform -.->|"Phase E"| storage["Object storage (S3-compatible)"]
```
*Today only the platform box exists, with the observability stack beside it. Dotted lines are planned.*

## 2. Containers — what actually runs (docker compose)

```mermaid
flowchart TB
  user["you / client"] --> app
  subgraph core["core (always)"]
    app["app<br/>(monolith: all services)"]
    pg[("postgres<br/>schema per service")]
    rd[("redis")]
    prov["db-provision (job)"]
    mig["migrate-&lt;service&gt; (jobs)"]
    prov --> mig --> app
    app --- pg
    app --- rd
  end
  subgraph obs["profile: obs"]
    col["otel-collector"]
    tempo["tempo"] 
    loki["loki"]
    prom["prometheus"]
    am["alertmanager"]
    graf["grafana"]
    exp["postgres / redis / blackbox exporters"]
  end
  subgraph tools["profile: tools"]
    mail["mailpit"]
    adm["adminer"]
  end
  app -->|"OTLP"| col
  col --> tempo & loki & prom
  exp --> prom
  prom --> am
  graf --> tempo & loki & prom
  adm --- pg
```

## 3. Components — inside the monolith process

```mermaid
flowchart TB
  uv["uvicorn"] --> mw["ObservabilityMiddleware<br/>(request id, app.service, access log, latency)"]
  mw --> eh["Error handlers<br/>(uniform error body)"]
  eh --> routers
  subgraph routers["Routers (mounted by create_application)"]
    health["/livez /readyz /startupz"]
    pub["/api/v1/&lt;service&gt;/…"]
    internal["/internal/v1/&lt;service&gt;/…<br/>(service principals only)"]
  end
  pub --> uc["Use cases (application/)"]
  internal --> uc
  uc --> dom["Domain rules"]
  uc --> uow["Unit of work (infrastructure/db)"]
  uow --> db[("Postgres schema")]
  uow --> ob["Outbox table"]
  relay["OutboxRelay (background)"] --> ob
  relay --> bus["InProcessEventBus"]
  bus --> handlers["Event handlers (other services)"]
  composition["Composition root<br/>create_application + wiring"] -. "provides / binds" .-> uc
```

## 4. Library dependencies — who may import whom

```mermaid
flowchart BT
  core["platform_core"]
  obs["platform_observability"] --> core
  ev["platform_events"] --> core
  ev --> obs
  http["platform_http"] --> core
  http --> ev
  http --> obs
  sec["platform_security"] --> core
  sec --> obs
  svc["services/&lt;name&gt;/service"] --> http
  svc --> sec
  svc --> ev
  svc --> obs
  svc --> core
  con["services/&lt;name&gt;/contracts"] --> http
  con --> ev
  con --> core
  svc --> con
  mono["apps/monolith"] --> http
  mono --> sec
```
*Arrows point from importer to imported. Libraries never import services (rule B-3); services never import each other (B-1); only `apps/` wires services together (B-4).*

## 5. Start-up sequence

```mermaid
sequenceDiagram
  autonumber
  participant D as docker compose
  participant PG as postgres
  participant P as db-provision
  participant M as migrate jobs (one per service)
  participant A as app (create_application)
  D->>PG: start and wait until healthy
  D->>P: run provision.sql (roles + schemas)
  P-->>D: exit 0
  D->>M: alembic upgrade head (per service)
  M-->>D: exit 0
  D->>A: start container
  A->>A: setup() observability, then load_modules() via entry points
  A->>A: module.provide(container), wiring(), register_event_handlers()
  A->>A: lifespan: on_startup(), start OutboxRelay per service
  A-->>D: /readyz = 200 → healthy
```

## 6. Who owns which data

```mermaid
flowchart LR
  subgraph one["One PostgreSQL server"]
    sa[("schema auth<br/>role auth")]
    su[("schema users<br/>role users")]
    sf[("schema files<br/>role files")]
    sn[("schema notifications<br/>role notifications")]
  end
  A["auth service"] --> sa
  U["users service"] --> su
  F["files service"] --> sf
  N["notifications service"] --> sn
  U -. "by contract only" .-> F
  A -. "event: auth.user_registered.v1" .-> U
```
*Solid lines are the only data access. Dotted lines are the only cross-service communication: contracts and events. No joins, no foreign keys across schemas.*

## 7. Extraction: before and after

```mermaid
flowchart LR
  subgraph before["Before: one process"]
    m1["monolith"] --- a1["auth"]
    m1 --- f1["files"]
    f1 -. "FilesApiImpl (in-process)" .- a1
  end
  subgraph after["After: files extracted"]
    m2["monolith"] --- a2["auth"]
    m2 -. "FilesHttpClient → HTTP" .-> fsvc["files-service<br/>(own repo, own DB)"]
    m2 -. "events via broker" .- fsvc
  end
  before ==> after
```
*What changes: one binding in `wiring.py`, the DB URL, and the event bus target. Business code and tests don't change — that is the whole point of the architecture.*

## 8. Where a signal goes (telemetry)

```mermaid
flowchart LR
  code["your code"] --> logs["JSON log line"]
  code --> span["span"]
  code --> metric["metric point"]
  logs -->|"stdout + OTLP"| col["collector"]
  span -->|OTLP| col
  metric -->|OTLP| col
  col --> loki["Loki"] & tempo["Tempo"] & prom["Prometheus"]
  loki & tempo & prom --> graf["Grafana (linked by trace_id)"]
```

## 9. Sending a notification, with failover

```mermaid
sequenceDiagram
  participant C as Caller (Auth, later)
  participant U as SendNotification
  participant D as notifications schema
  participant G as NotificationGateway
  participant S as smtp (Mailpit)
  participant K as console
  C->>U: NotificationsApi.send(email, otp)
  U->>D: tx 1 - rate limit + idempotency + INSERT pending
  U->>G: deliver(message)
  G->>S: send (timeout)
  S-->>G: unavailable
  G->>K: send
  K-->>G: accepted
  G-->>U: sent via console, 2 attempts
  U->>D: tx 2 - UPDATE sent
  U-->>C: SendResult(sent)
```
*Two short transactions around the slow provider call; a total failure additionally writes `notifications.delivery_failed.v1` to the outbox in tx 2. See [Phase B](../phase-b/01-notifications-concepts-and-design.md).*

## 🧪 Labs
1. Redraw diagram 5 for the case where `migrate-<service>` fails. What does the app do? What does `docker compose up --wait` print?
2. Add a new box for "Auth" in diagram 3 showing where `JwtVerifier` runs (hint: it's a dependency of the router, not a separate service).
3. Using diagram 4, explain why `platform_core` can't import `platform_events`.
<details><summary>Solutions</summary>

1. The app never starts (its `depends_on` condition isn't met); `up --wait` reports the failed dependency container and exits non-zero. 2. In the router layer: `Depends(get_principal)` verifies the bearer token locally before the use case runs. 3. It would create an import cycle (events already depend on core); layering keeps `platform_core` at the bottom.
</details>

## 🎯 Interview Questions
1. **Describe the system in two minutes using only diagrams 2, 3 and 6.** *Containers run Postgres/Redis/app plus an optional observability stack; inside the app, requests flow middleware → routers → use cases → unit of work → schema with an outbox relay publishing events; each service owns exactly one schema and talks to others only via contracts and events.*
2. **What changes when you extract a service?** *One wiring binding (to an HTTP client), the database URL, and the event bus target — see diagram 7.*
3. **Why can't libraries import services?** *Dependencies must point inward/downward; a library that knows a service can't be shared by the others and creates cycles.*

## ✅ Self-check
- [ ] I can draw diagrams 2, 3 and 6 from memory.
- [ ] I can explain every arrow's direction in diagram 4.
- [ ] I can narrate diagram 5 including what happens on failure.

**Next:** [KT · 05 — Decision log in plain English →](05-decision-log-in-plain-english.md)
