# F · 03 — Databases for Backend Developers

**Goal:** understand tables, transactions, indexes, N+1 queries, row locking and per-service schemas — the database ideas our unit of work, outbox and migrations are built on.
**Prerequisites:** [F · 01](01-python-for-this-codebase.md). **Time:** 1.5 hours.
Examples use SQLite (for portability) and a throw-away PostgreSQL 16 container (for the Postgres-only features). All outputs are real.

---

## 3.1 The mental model

A **relational database** stores data in **tables** (rows × columns). You talk to it in **SQL**. Three promises make it trustworthy:

| Promise | Meaning |
|---|---|
| **Atomic** | A group of changes (a *transaction*) happens completely or not at all |
| **Consistent** | Rules you declare (types, `NOT NULL`, `CHECK`, foreign keys) are never violated |
| **Isolated** | Concurrent transactions don't see each other's half-finished work |
| **Durable** | Once committed, it survives a crash |

(That's **ACID**.) Our entire "event + data in one transaction" outbox pattern rests on the **A**.

## 3.2 Atomicity — the money-transfer lesson

```python
db.execute("create table acct(name text primary key, balance int check (balance >= 0))")
# alice has 100, bob has 0
def transfer(amount):
    with db:                                    # ONE transaction: commit on success, rollback on error
        db.execute("update acct set balance = balance + ? where name='bob'",   (amount,))
        db.execute("update acct set balance = balance - ? where name='alice'", (amount,))  # may break the CHECK
transfer(150)
```
```
transfer(150) failed: CHECK constraint failed: balance >= 0
balances after the failure: {'alice': 100, 'bob': 0} <- bob's +150 was rolled back too
balances after transfer(40): {'alice': 60, 'bob': 40}
```
Bob received +150 *before* Alice's debit failed — and the database **undid it**. Without a transaction, money would have appeared from nowhere.

> 💡 **Learning Thought — a transaction is how you make "two things" behave like "one thing".** In this repo the two things are *"save the business data"* and *"record the event to announce it"* ([A1 · 05](../phase-a1/05-a-request-end-to-end.md)).

## 3.3 The unit of work in code

Our use cases open a unit of work (UoW) = a session + a transaction. The behaviour, verified with SQLAlchemy async:

```python
async with sessions() as s:                       # 1. commit  -> persisted
    await s.execute(insert(authors).values(id=100, name="kept")); await s.commit()
try:
    async with sessions() as s:                   # 2. exception before commit -> rolled back
        await s.execute(insert(authors).values(id=101, name="lost"))
        raise RuntimeError("something failed before commit")
except RuntimeError: pass
# afterwards:  rows with id>=100: ['kept']
```
The generated `SqlUnitOfWork` ([template](../../../tools/templates/service/service/src/__service___service/infrastructure/db/uow.py.tmpl)) does exactly this: roll back on exception, close the session always, commit only when asked.

## 3.4 Indexes — why a query is fast or slow

Without an index the database reads **every row** (a *scan*); with one it jumps straight to matches (a *search*). Real plan from 20 000 rows:

```
before index: SCAN orders
after index:  SEARCH orders USING INDEX ix_orders_customer (customer=?)
```
(`EXPLAIN` / `EXPLAIN QUERY PLAN` is how you check.) Rules of thumb: index columns you filter/join/sort by; every index slows writes and costs space, so don't index everything; our outbox has a **partial index** on only the *pending* rows
(`WHERE published_at IS NULL AND failed_at IS NULL`) so the relay's "what's waiting?" query stays fast no matter how many old rows exist ([migration](../../../tools/templates/service/service/migrations/versions/0001_initial.py.tmpl)).

## 3.5 The N+1 trap

Loading a list and then querying inside a loop turns **1** query into **N+1**:

```python
for a in (await c.execute(select(authors))).all():              # 1 query ...
    await c.execute(select(books).where(books.c.author_id == a.id))   # ... + 1 per author
```
```
N+1 style:   queries = 21        (20 authors)
single join: queries = 1
```
Harmless on your laptop (microseconds each), painful in production (each is a network round-trip). The same shape across **services** is worse — which is why contract methods are *batchable* (rule C-3).

> ⚠️ **Trap — a loop that calls the database (or another service) per item.** If you see `for x in xs: await something(x)`, ask whether one query / one batch call could replace it.

## 3.6 Row locking — how multiple relays share a queue

Our outbox relay claims rows with `SELECT … FOR UPDATE SKIP LOCKED`. Why? Two workers must never process the same row. Real experiment (two connections, 4 pending jobs):

```
worker A claims: [id=1, id=2]                          (inside an open transaction → rows locked)
worker B, plain FOR UPDATE NOWAIT (row is locked by A):
    LockNotAvailableError - could not obtain lock on row in relation "jobs"
worker B, FOR UPDATE SKIP LOCKED:
    B claims: [id=3, id=4]   <- different rows, no waiting
```
| Clause | Behaviour when a row is locked by someone else |
|---|---|
| `FOR UPDATE` | **wait** until the other transaction ends |
| `FOR UPDATE NOWAIT` | fail immediately |
| `FOR UPDATE SKIP LOCKED` | silently **skip** it and take the next free row |

That is a safe, database-only work queue. (SQLite ignores it — it has one writer at a time — which is why SQLite is fine for unit tests but not a substitute for Postgres.)

## 3.7 Schemas and roles — one database, many private spaces

A PostgreSQL **schema** is a namespace inside a database. We give every service its own schema and its own login role (rules D-1…D-4). Real experiment — logging in *as the `notes` role*:

```
notes_role creates notes.t: ok
notes_role creates users.t: InsufficientPrivilegeError - permission denied for schema users
notes_role reads users.t:    InsufficientPrivilegeError - permission denied for schema users
```
The database itself enforces service boundaries. Code that reaches into another service's tables fails in development, not in an incident review.

## 3.8 Migrations — version control for the schema

A **migration** is a numbered script that changes the schema (`0001_initial` creates the outbox table). **Alembic** runs them in order and records the current version in a table (`<schema>.alembic_version`). Rules we follow:

- Each service has its **own** migration history and runs it as its own job ([A2 · 02](../phase-a2/02-compose-the-whole-system.md)).
- Migrations are **frozen snapshots**: they never import application code (code changes; history must not).
- Prefer **additive** changes (add a nullable column, backfill, then enforce). Dropping/renaming in one step breaks the version of the app that is still running during a deploy.
- **Never trust "exit code 0".** We once had a migration job that succeeded and created nothing ([A2 · 04](../phase-a2/04-what-the-live-run-taught-us.md)).

## 3.9 SQLAlchemy in one page

| Piece | Meaning | Where |
|---|---|---|
| `MetaData`, `Table` | Description of tables (Core API) | `infrastructure/db/models.py` (`make_metadata(schema)`, `make_outbox_table`) |
| `AsyncEngine` | The connection pool | `platform_core.db.create_engine` |
| `AsyncSession` | A transaction scope + identity map | opened by `SqlUnitOfWork` |
| `async_sessionmaker` | Factory for sessions | `create_session_factory` |
| `schema_translate_map` | Rename a schema at run time | lets SQLite tests ignore the Postgres schema name |

We use **explicit SQL-building (Core)** for the outbox and keep ORM entities out of contracts (rule L-5).

## 🧪 Labs
1. In SQLite, add `create index` to the `orders` demo for a *multi-column* filter (`customer`, `total`). Use `explain query plan` to prove it is used for `where customer='c7' and total > 100`.
2. Write the N+1 example against a table of 1 000 authors and time both versions (`time.perf_counter`). Which is faster, and by how much on your machine?
3. In Postgres (`docker run --rm -e POSTGRES_PASSWORD=pw -p 15432:5432 postgres:16.4`), run the `SKIP LOCKED` experiment with *three* workers and 6 jobs. Which rows does each get?
<details><summary>Solutions</summary>

1. `create index ix on orders(customer, total)`; the plan reads `SEARCH orders USING COVERING INDEX ix (customer=? AND total>?)` (*covering* = the index alone has every column the query needs, so the table isn't even touched). 2. Expect the single query to be tens to hundreds of times faster on a real network database; in-memory SQLite narrows the gap. 3. Each worker gets a disjoint pair, e.g. `[1,2]`, `[3,4]`, `[5,6]` — none waits.
</details>

## 🎯 Interview Questions
1. **Explain ACID with an example.** *A bank transfer: both updates commit or neither (atomic); constraints like non-negative balance hold (consistent); concurrent transfers don't see partial results (isolated); committed transfers survive a crash (durable).*
2. **What is an index and what is its cost?** *A data structure that makes lookups on a column fast; it slows writes and uses space, so index what you query by.*
3. **What is the N+1 problem and how do you fix it?** *One query for a list plus one per item; fix with a join, `IN (…)` batch query, or eager loading.*
4. **Why `FOR UPDATE SKIP LOCKED` for a job table?** *Competing workers each claim different rows without blocking each other or double-processing.*
5. **Why a separate schema and role per service?** *Enforces data ownership in the database itself and makes extraction a dump/restore plus a changed connection string.*
6. **Why must migrations not import application code?** *Application code evolves; a migration must reproduce the same change forever.*

## ✅ Self-check
- [ ] I can explain what would go wrong in the transfer example without a transaction.
- [ ] I can read an `EXPLAIN` line and say whether it scans or searches.
- [ ] I can recognise an N+1 pattern in code.
- [ ] I can explain `SKIP LOCKED` and where we use it.

## 📚 Further reading
- PostgreSQL — Transactions tutorial: <https://www.postgresql.org/docs/16/tutorial-transactions.html>
- PostgreSQL — Explicit locking (`SKIP LOCKED`): <https://www.postgresql.org/docs/16/explicit-locking.html>
- Use The Index, Luke!: <https://use-the-index-luke.com/>
- SQLAlchemy 2 — asyncio extension: <https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html>
- Alembic tutorial: <https://alembic.sqlalchemy.org/en/latest/tutorial.html>

**Next:** [F · 04 — Testing guide →](04-testing-guide.md)
