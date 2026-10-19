# KT · 05 — Decision Log in Plain English

**Goal:** understand *why* the project looks the way it does — each important decision with the alternatives we rejected, the honest trade-off, and what would make us revisit it.
**How to use:** when you're tempted to "simplify" something, look it up here first. The formal, numbered versions live in [`docs/architecture`](../../architecture/README.md) (decisions A1–A20 and the STANDARDS rules); this page is the human explanation.

> **Format of every entry:** *Situation → Decision → Alternatives we rejected → Trade-off we accepted → Revisit when…*

---

## D1 · A modular monolith, not microservices (yet)
- **Situation:** several capabilities (Auth, Users, Files, Notifications) and no data on which will need to scale separately.
- **Decision:** one deployable app built from strictly separated services.
- **Rejected:** (a) one tangled app (cheap now, impossible to split later); (b) microservices from day one (heavy operations cost with no evidence of need).
- **Trade-off:** we pay a *discipline tax* (contracts, ports, rules checked by tools) even though everything is in one process.
- **Revisit when:** a service has a distinct scaling profile, a separate team, fault-isolation or compliance needs ([extraction playbook triggers](../../architecture/EXTRACTION_PLAYBOOK.md)).

## D2 · Services talk only through contracts and events
- **Situation:** the cheapest way to call another service is to import its code.
- **Decision:** forbid it (rule B-1) — the only cross-service import is `<name>_contracts`, and CI enforces it.
- **Rejected:** convention-only ("please don't import internals").
- **Trade-off:** more files (ports, adapters, DTOs) for every cross-service interaction.
- **Revisit when:** never for the rule itself; we may *simplify the tooling* if friction proves unnecessary.

## D3 · `service/` and `contracts/` are sibling packages
- **Situation:** we wanted `contracts/` *inside* each service folder.
- **Decision:** make them siblings under `services/<name>/`.
- **Why:** uv refuses a workspace member nested inside another member (real error: *"Project is contained in non-workspace project"*). The sibling layout also makes the public/private split visible in the tree.
- **Revisit when:** uv supports nested members (then it's cosmetic).

## D4 · uv workspace with an explicit, generated member list
- **Situation:** globs like `services/*` fail when a matching folder has no `pyproject.toml` (our planning-docs folders).
- **Decision:** list members explicitly; a tool regenerates the block from disk.
- **Rejected:** hand-maintained list (drifts), globs (break on stray folders).

## D5 · One PostgreSQL server, one schema + one role per service
- **Situation:** separate databases per service are expensive now; a shared schema blocks extraction.
- **Decision:** one server; each service owns a schema and a login role that can't touch other schemas (proved by a "permission denied" test).
- **Trade-off:** a noisy neighbour could still slow the shared server.
- **Revisit when:** extraction (dump the schema, change one URL) or load demands separate servers.

## D6 · Transactional outbox from day one
- **Situation:** "save then publish" can lose events on a crash.
- **Decision:** write the event to an outbox table in the same transaction; a relay publishes it.
- **Rejected:** publishing straight to an in-memory bus (hides at-least-once bugs until we have a real broker).
- **Trade-off:** a little latency (relay polls every 0.5 s) and an extra table per service.

## D7 · Migrations run as jobs, never at app start-up
- **Situation:** several app replicas would race to migrate.
- **Decision:** a `migrate-<service>` job per service, gated before the app starts.
- **Lesson learned the hard way:** a job that exits 0 can still have rolled back everything (transaction handling in Alembic); we verify *results* in the stack check.

## D8 · OpenTelemetry end to end, through a Collector
- **Situation:** observability vendors differ and change.
- **Decision:** the app speaks only OTLP to one Collector; backends (Tempo/Loki/Prometheus locally) sit behind it.
- **Rejected:** vendor agents/SDKs in code (lock-in), the app pushing directly to each backend.
- **Trade-off:** one more container, one more config to understand.

## D9 · `app.service` on every signal
- **Situation:** inside the monolith, OpenTelemetry's `service.name` is the same for Auth and Users.
- **Decision:** add our own attribute naming the *logical* service on logs, spans and metrics.
- **Why:** dashboards and alerts keep working unchanged after a service is extracted.

## D10 · Metrics only from our middleware; FastAPI's native metrics and logs switched off
- **Situation:** FastAPI 0.146 ships its own OpenTelemetry. With our middleware, every request was counted **twice** (one series without `app.service`).
- **Decision:** keep FastAPI's native *spans*; switch off its metrics and logs.
- **Lesson:** two libraries "helpfully" instrumenting the same thing — decide who owns each signal. Found by printing real data, not by tests.

## D11 · Structured JSON logs to stdout *and* OTLP; redaction is automatic
- **Decision:** one JSON object per line, constant `event` names, secrets scrubbed by a processor (plus a Collector safety net).
- **Rejected:** free-text log messages (unqueryable, leak data).
- **Trade-off:** a bit more ceremony per log call; huge gain in searchability and safety.

## D12 · Metric labels are closed sets
- **Decision:** each metric declares allowed attribute names/values; strict locally, lenient in production.
- **Why:** unbounded labels (ids, URLs) explode storage; a typo must never take production down.

## D13 · SLO burn-rate alerts generated from `slo.yaml`; runbook required
- **Decision:** page on *how fast the error budget burns*, not on CPU or error counts; the generator refuses to run without a runbook section per alert.
- **Rejected:** hand-written threshold alerts (noisy, inconsistent).

## D14 · Everything a service needs to operate travels inside its folder
- **Decision:** dashboards, SLOs, alerts, runbook, migrations, Dockerfile live under `services/<name>/`.
- **Why:** extraction should be `git filter-repo --subdirectory-filter services/<name>`, not an archaeology dig.

## D15 · Services are discovered via entry points
- **Decision:** each service registers `befastapi.services`; the monolith loads whatever is installed.
- **Why:** adding a service never edits shared code (the Open/Closed principle in practice).

## D16 · One Docker image for every app
- **Decision:** one multi-stage, non-root image; the container command picks the app.
- **Trade-off:** the image contains all installed services even when you run one; fine for a monolith, revisit per extracted service (each keeps its own Dockerfile).

## D17 · `db-provision` job instead of Postgres init scripts
- **Why:** init scripts run only on first volume creation; a service added later would never get its schema.

## D18 · A generator plus a *scaffold check* in CI
- **Decision:** new services come from `tools/new_service.py`; CI generates a throw-away service and runs every gate on it.
- **Why:** templates rot silently; a guard that generates-validates-deletes keeps the starting point correct (it caught a real bug on its first run).

## D19 · Documentation is part of "done"
- **Decision:** each phase ships a beginner learning chapter whose commands were *actually run*; `make docs-check` guards links, anchors, the codebase map and structure.
- **Why:** this project is meant to be learned by newcomers; wrong docs are worse than none.

## D20 · Prove it on the real stack
- **Decision:** `make stack-check` boots everything and verifies log → trace → metric correlation.
- **Why:** it found ten problems (missing production dependency, double-formatting log handler, silent migration rollback, wrong metric names …) that unit tests could not. See [A2 · 04](../phase-a2/04-what-the-live-run-taught-us.md).

---

## How to challenge a decision
1. Find its entry here and in STANDARDS/ARCHITECTURE (rule IDs).
2. Write down the new situation (what changed since the decision).
3. Propose an **ADR** (`docs/architecture/ADR/NNNN-…`) with owner and, if it's a waiver, an **expiry date**.
4. Update this page so the next newcomer reads the new reasoning.

## 🎯 Interview Questions
1. **Why not microservices from the start?** *No evidence yet of what needs independent scaling; the operational cost (network failures, versioning, observability) is paid up front. We keep the exit cheap instead.*
2. **Why enforce architecture with tools instead of reviews?** *Reviews miss indirect imports and fatigue; a failing check on every PR is consistent and costs nothing per review.*
3. **Name one decision that was reversed or refined after real-world feedback.** *Disabling FastAPI's native metrics (double counting), `db-provision` job vs init scripts, siblings instead of nested packages, committing placeholder folders because Docker creates missing mounts as root.*
4. **Why generate alert rules from `slo.yaml`?** *Consistency and correctness (windows, burn rates, runbook links) without copy-paste, and the rules stay with the service.*

## ✅ Self-check
- [ ] For any three decisions above, I can state the alternative we rejected and the trade-off we accepted.
- [ ] I know how to propose changing a decision.

**Next:** [KT · 06 — Debugging playbook →](06-debugging-playbook.md)
