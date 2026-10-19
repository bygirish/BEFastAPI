# Glossary

Plain-English definitions, in the order you will meet them. 🔗 = see the chapter where it matters most.

## Architecture
| Term | Meaning |
|---|---|
| **Monolith** | One program deployed as a single unit. Simple to run and debug; everything can reach everything (which is also its danger). |
| **Microservices** | Many small programs, each deployed separately and talking over the network. Scales teams and load independently, but adds network failures, versioning and operations cost. |
| **Modular monolith** | A monolith whose parts (modules) have hard boundaries, so it behaves like several small services living in one process. This project. 🔗 [01](phase-a1/01-the-big-picture.md) |
| **Service** (in this repo) | A business capability with its own code, data and public contract — e.g. Auth, Users. A folder under `services/`, a potential future repo. |
| **Contract** | The *small, public* surface of a service: data shapes (DTOs), interfaces (Protocols), events, errors, an HTTP client. Everything else is private. 🔗 [03](phase-a1/03-boundaries-contracts-and-layers.md) |
| **DTO** | Data Transfer Object — a plain data class that crosses a boundary (here: a Pydantic model). Never a database object. |
| **Port** | An interface *you own* describing what you need from the outside ("give me a signed URL"). |
| **Adapter** | The code that plugs a port into a real thing (another service, a vendor SDK, a database). Swappable. |
| **Ports & adapters (hexagonal)** | Architecture style: business code talks to ports; adapters translate to the outside world. |
| **Composition root** | The single place that decides which implementations are plugged into which ports. Here: `apps/*`. |
| **Dependency injection (DI)** | Passing the things a class needs *into* it instead of having it create or import them. Makes code testable and swappable. |
| **Layers** | `api → application → domain`, with `infrastructure` plugging in from the side. Lower layers never import higher ones. |
| **Use case** | One business action as a class/function (`Ping`, later `RegisterUser`). Orchestrates; contains no HTTP or SQL. |
| **Domain** | Pure business rules and errors with no framework imports. |
| **Unit of work (UoW)** | "One transaction per use case": everything it writes is committed together or not at all. |
| **Repository** | An object that hides how entities are stored/loaded. |
| **Extraction** | Moving a service out of the monolith into its own repo/deployment. 🔗 [EXTRACTION_PLAYBOOK](../architecture/EXTRACTION_PLAYBOOK.md) |
| **Distributed monolith** | The anti-pattern: services so tightly coupled (chains of synchronous calls) that you get microservice pain with monolith coupling. |

## Messaging
| Term | Meaning |
|---|---|
| **Integration event** | A *fact* that happened ("ping received"), named `service.noun_verb.v1`, published for other services to react to. |
| **Event bus** | The thing that delivers events to subscribers (in-process today; a broker like Redis Streams/Kafka later). |
| **Transactional outbox** | Write the event into a table **in the same transaction** as your data; a background relay publishes it afterwards. Prevents "saved but never announced". 🔗 [05](phase-a1/05-a-request-end-to-end.md) |
| **Relay** | The background loop that moves outbox rows to the event bus. |
| **At-least-once delivery** | An event may arrive more than once, never zero times (after retries). |
| **Idempotent** | Doing it twice has the same effect as once. Event handlers must be idempotent. |
| **Dead letter** | A message that failed too many times and is parked for a human to look at. |

## Security
| Term | Meaning |
|---|---|
| **JWT** | JSON Web Token — a signed string carrying claims (who you are, which org, your roles). |
| **RS256 / JWKS** | The token is signed with a *private* key; anyone can verify it with the *public* key, published as a JSON Web Key Set at a URL. |
| **Principal** | The authenticated caller after verification (user or another service). |
| **RBAC** | Role-Based Access Control — permissions are granted through roles. |
| **Redaction** | Automatically removing secrets/personal data (passwords, OTPs, tokens) from logs and traces. |

## Observability
| Term | Meaning |
|---|---|
| **Log** | A timestamped line describing an event. Ours are JSON, one per line. |
| **Metric** | A number tracked over time (requests/second, latency). Cheap to store, great for alerts. |
| **Trace / span** | A trace is the story of one request; spans are its timed steps (nested). |
| **Correlation** | Linking the three: the same `trace_id` appears in logs, spans and (via exemplars) metrics. |
| **OpenTelemetry (OTel)** | The vendor-neutral standard (API, SDK, wire protocol OTLP) for all three signals. |
| **RED metrics** | **R**ate, **E**rrors, **D**uration of requests — the first three things you want on a dashboard. |
| **Cardinality** | The number of distinct label combinations on a metric. High cardinality (e.g. a user id label) explodes cost. |
| **SLI / SLO** | A measured indicator (e.g. % of fast requests) / the target for it (99 %). |
| **Burn rate** | How fast you are spending the error budget; alerts fire on fast burn. |
| **`app.service`** | Our attribute on every signal naming the *logical* service (`auth`), even while everything runs in one process. |

## Python tooling
| Term | Meaning |
|---|---|
| **Package / module** | A folder/file of importable Python code. |
| **`pyproject.toml`** | The one config file describing a project: name, dependencies, tool settings. 🔗 [02](phase-a1/02-monorepo-and-uv.md) |
| **src layout** | Code lives in `src/<package>/` so tests import the *installed* package, not the working folder. |
| **Virtual environment (`.venv`)** | A private folder of installed packages for one project. |
| **uv** | A fast Python package/project manager (installs, locks, runs). |
| **Workspace** | Several packages in one repo sharing one lockfile and environment. |
| **Lockfile (`uv.lock`)** | The exact versions that were resolved, so everyone installs the same thing. |
| **Editable install** | The environment points at your source folder, so code edits take effect without reinstalling. |
| **Entry point** | A named hook in package metadata. We use group `befastapi.services` so the monolith can *discover* services without importing them by name. |
| **Ruff** | Linter + formatter. **mypy** — static type checker. **import-linter** — checks which packages may import which. 🔗 [08](phase-a1/08-quality-gates-and-ci.md) |
| **Pydantic** | Library for typed data models and validation (used for DTOs, events, settings). |
| **ASGI / middleware** | The async web-server interface FastAPI sits on / code wrapping every request. |
| **Lifespan** | FastAPI's start-up and shut-down hook. |
| **Alembic** | Database migration tool — versioned scripts that evolve a schema. |
| **Schema (Postgres)** | A namespace inside a database. Each service owns exactly one. |
