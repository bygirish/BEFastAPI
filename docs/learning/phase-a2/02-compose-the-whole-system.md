# A2 · 02 — Docker Compose: Running the Whole System

**Goal:** bring up the database, cache, migrations, the application, the observability stack and developer tools with **one command**, and understand every moving part.
**Prerequisites:** [01 · Docker for beginners](01-docker-for-beginners.md). **Time:** 1–1.5 hours.
Outputs are real (captured from a run with a generated service called `notes`).

---

## 2.1 What Compose is

A single container is easy. Our system is **14 cooperating containers**. **Docker Compose** lets you describe them all in one file
(`docker-compose.yml`) and start, stop and inspect them together.

| Compose idea | Meaning | In our file |
|---|---|---|
| **service** | One kind of container | `postgres`, `redis`, `app`, `grafana` … |
| **network** | A private virtual LAN; containers reach each other **by service name** (`postgres:5432`) | `edge`, `backend`, `obs` |
| **volume** | Persistent storage | `pg-data`, `grafana-data` … |
| **profile** | A label that switches optional services on/off | `obs`, `tools` |
| **`depends_on` + condition** | Start ordering that waits for *health* or *completion* | `service_healthy`, `service_completed_successfully` |
| **one-shot job** | A container that does a task and exits | `db-provision`, `migrate-<service>` |
| **anchor / merge key** | YAML reuse: `&migrate` then `<<: *migrate` | the migration jobs |
| **`${VAR:-default}`** | Environment substitution with a default | ports, passwords |

## 2.2 The startup order we built

```mermaid
flowchart TD
  PG[("postgres<br/>healthy")] --> PROV["db-provision<br/>(job) roles + schemas"]
  PROV --> MIG["migrate-&lt;service&gt;<br/>(job, one per service)"]
  RED[("redis<br/>healthy")] --> APP
  PROV --> APP
  MIG --> APP["app (monolith)<br/>healthy = /readyz ok"]
  subgraph obs["profile: obs"]
    COL["otel-collector"] --> TEMPO["tempo"] & LOKI["loki"] & PROM["prometheus"]
    GRAF["grafana"] --> TEMPO & LOKI & PROM
    PROM --> AM["alertmanager"]
    PGX["postgres-exporter"] & RDX["redis-exporter"] & BB["blackbox-exporter"]
  end
  subgraph tools["profile: tools"]
    MAIL["mailpit"] & ADM["adminer"]
  end
  APP -. "OTLP" .-> COL
```

> 💡 **Learning Thought — wait for *conditions*, never for *time*.** Old scripts say `sleep 10` and hope. Compose waits for "postgres reports healthy",
> then "the provisioning job exited 0", then "the migration job exited 0", then starts the app (rule **E-4**). If anything fails, nothing after it starts.

## 2.3 Using it

```bash
cp .env.example .env        # once; COMPOSE_PROFILES=obs,tools means "start everything"
make up                     # = sync generated assets, then: docker compose up -d --build --wait
make ps                     # status
make logs s=app             # follow one service
make down                   # stop, keep data
make reset                  # stop AND delete all volumes (fresh start)
```
Without a `.env`, only the **core** (postgres, redis, provisioning, migrations, app) starts. Profiles switch the rest on:

| Profile | Starts |
|---|---|
| *(none — core)* | postgres, redis, db-provision, migrate-*, app |
| `obs` | otel-collector, tempo, loki, prometheus, alertmanager, grafana, postgres-exporter, redis-exporter, blackbox-exporter |
| `tools` | mailpit (fake e-mail inbox), adminer (database browser) |

▶ **Try it** — the real result of `make up` (warm cache: 71 s including a rebuild check):
```
adminer              | Up
alertmanager         | Up
app                  | Up (healthy)
blackbox-exporter    | Up
db-provision         | Exited (0)        ← one-shot job: success
grafana              | Up
loki                 | Up
mailpit              | Up (healthy)
migrate-notes        | Exited (0)        ← one-shot job: success
otel-collector       | Up
postgres             | Up (healthy)
postgres-exporter    | Up
prometheus           | Up
redis                | Up (healthy)
redis-exporter       | Up
tempo                | Up
```
`Exited (0)` is *good* for the two job containers. Memory for the **whole** stack, measured with `docker stats`: app 78 MB, Grafana 86 MB, Postgres 56 MB, collector 50 MB, Tempo 41 MB, Loki 39 MB, Prometheus 27 MB … **≈ 0.46 GB total** — it fits comfortably on a small laptop.

## 2.4 One database, one schema per service

We run **one** Postgres server but give each service its **own role and its own schema** (rules **D-1…D-4**). The generated file `deploy/postgres/provision.sql`:

```sql
-- notes
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'notes') THEN
    CREATE ROLE notes LOGIN PASSWORD 'notes';
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS notes AUTHORIZATION notes;
ALTER ROLE notes SET search_path = notes;
```
It is **idempotent** (safe to run on every `up`), and it is run by the `db-provision` job.

> ⚠️ **Trap — why not Postgres "init scripts"?** Files in `/docker-entrypoint-initdb.d` run **only when the data volume is first created**. A service added next
> month would never get its schema unless you wiped the database. A job that runs on every `up` has no such cliff.

▶ **Try it** — what the database looks like afterwards:
```
schemas:        notes, public
tables (notes): alembic_version, outbox
alembic version: 0001
```
▶ **Try it** — prove the isolation (we connect *as the `notes` role* and try to write to someone else's space):
```
ERROR:  permission denied for schema public
```
That one line is rule D-4 working: a service's database user cannot touch anything outside its own schema. If a developer wrote SQL that reached into another service's tables, it would **fail here, in development**.

## 2.5 Migrations as jobs

Each service has its own **Alembic** environment and its own `migrate-<service>` job (rule **D-3**):

```yaml
migrate-notes:
  <<: *migrate                       # image, network, "wait for db-provision" come from the anchor
  command: ["alembic", "-c", "services/notes/service/migrations/alembic.ini", "upgrade", "head"]
  environment:
    NOTES_DATABASE_URL: postgresql+asyncpg://notes:notes@postgres:5432/befastapi
```
The app does **not** run migrations itself at start-up: with several replicas they would race each other, and it would mix "deploy code" with "change the schema".

### ⚠️ The migration that "succeeded" and created nothing
The first live run printed `Exited (0)` — then the app crashed: `relation "stackcheck.outbox" does not exist`. The job really had run, but **rolled everything back**:

```python
connection.execute(text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"), ...)   # auto-starts a transaction!
configure(connection)
with context.begin_transaction():      # Alembic sees "a transaction is already open" → does NOT commit
    context.run_migrations()
# connection closes → implicit ROLLBACK
```
**Fix:** `connection.commit()` right after the schema check, so Alembic starts and commits its own transaction (`tools/templates/service/service/migrations/env.py.tmpl`).

> 💡 **Learning Thought — exit code 0 only means "the program ended", not "the work was done".** Verify outcomes (the table exists), not just exit codes. SQLite-based unit tests
> could never have caught this; only a real Postgres run did. (Our unit tests create tables directly and skip migrations.)

## 2.6 Generated blocks (rule E-1)

The migration jobs, the app's `*_DATABASE_URL` variables and its `depends_on` entries are **written by `tools/sync_workspace.py`** from the services on disk:

```yaml
  # >>> generated:migrate-jobs (tools/sync_workspace.py)
  migrate-notes:
    <<: *migrate
    ...
  # <<< generated:migrate-jobs
```
Adding a service never means hand-editing Compose (CI checks `sync_workspace.py --check`). Removing the service and re-syncing removes its job.

## 2.7 Ports, secrets, and configuration

- **Configuration only via environment** (`.env`, documented in `.env.example`; rule **E-3**). `${APP_PORT:-8000}` means "use APP_PORT, else 8000".
- Every credential in this stack is **local-only** (`postgres/postgres`, `notes/notes`, `admin/admin`). They are in the repo on purpose; they protect nothing real.
- **Networks**: `edge` (reachable from your machine: app, Grafana), `backend` (app ↔ Postgres/Redis), `obs` (telemetry). The database is published to the host on 5432 only for convenience.

⚠️ **Trap — "the smoke test says 404 on `/readyz` but the app is healthy".** Something *else* was already listening on host port 8000 (a different uvicorn app on this very machine, PID 20294).
Docker published the container on `0.0.0.0:8000`, but `localhost` resolved to the more specific `127.0.0.1:8000` listener — the wrong server. Diagnose with
`lsof -nP -iTCP:8000 -sTCP:LISTEN`; fix with `APP_PORT=18000 make stack-check` (or set `APP_PORT` in `.env`).

⚠️ **Trap — Docker creating root-owned folders.** If a bind-mounted host folder doesn't exist, Docker creates it **as root**. Our `deploy/observability/generated/{rules,dashboards}` are committed as empty
placeholders (`.gitkeep`) for exactly that reason.

## 🧪 Labs
1. Run `make up`, then `docker compose ps -a`. Which containers are *supposed* to be `Exited (0)`?
2. `make reset && make up`. Why is the second start slower than a plain `make down && make up`?
3. Set `COMPOSE_PROFILES=` (empty) in `.env` and `make up`. What is missing? What still works?
4. Connect with Adminer (`http://localhost:8080`, system PostgreSQL, server `postgres`, user `notes`, password `notes`, database `befastapi`). Which schemas can you see?
<details><summary>Solutions</summary>

1. `db-provision` and every `migrate-*`. 2. `reset` deletes the volumes, so Postgres re-initialises and all migrations run again, and Grafana/Prometheus lose their data. 3. Only the core runs: no Grafana/Tempo/Loki/Prometheus, no Mailpit/Adminer; the app still serves requests (its telemetry exporter just can't reach a collector — and the app doesn't care).
4. Only `notes` (plus the harmless `public`): the role has no rights elsewhere.
</details>

## 🎯 Interview Questions
1. **Compose vs Kubernetes?** *Compose describes containers on one machine (great for local dev/CI); Kubernetes schedules them across a cluster with scaling, self-healing and rollouts. Our service boundaries and 12-factor config carry over to both.*
2. **Why a migration *job* rather than migrate-on-start?** *Single, ordered execution; no race between replicas; separate "change schema" from "start serving"; failures block the deploy visibly.*
3. **What does `depends_on: condition: service_completed_successfully` do?** *Starts the dependent only after the other container has exited with code 0 — used for one-shot jobs such as migrations.*
4. **Why schema-per-service in one database?** *Cheap to run today, yet each service has its own tables, role and migration history — so extraction is a dump/restore plus a changed connection string.*
5. **A job exits 0 but its tables are missing. What happened?** *A transaction was never committed (ours: Alembic was handed a connection with an already-open transaction). Verify results, not exit codes.*

## ✅ Self-check
- [ ] I can draw the startup order and say what each arrow waits for.
- [ ] I know what profiles do and which one starts Grafana.
- [ ] I can explain why `db-provision` is a job and not an init script.
- [ ] I can show that a service's database role cannot reach another schema.

## 📚 Further reading
- Docker Compose — *Profiles*: <https://docs.docker.com/compose/how-tos/profiles/>
- Docker Compose — `depends_on`: <https://docs.docker.com/compose/how-tos/startup-order/>
- Alembic — *Using asyncio with Alembic*: <https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic>
- PostgreSQL — Schemas and privileges: <https://www.postgresql.org/docs/16/ddl-schemas.html>

**Next:** [03 · The observability stack in practice →](03-the-observability-stack-in-practice.md)
