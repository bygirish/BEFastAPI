# Assessment · 02 — Capstone Project: the **Bookmarks** Service

**Goal:** prove you can build a complete, rule-abiding service end to end — domain rules, database and migration, use cases, public HTTP API, contract (in-process **and** HTTP), events, metrics, tests and docs — and run it on the real stack.
**Prerequisites:** Phase A1/A2 chapters and the Foundations track. **Time:** 1–2 days.
**This capstone was solved first by the authors** (reference solution: 24 tests, all quality gates, and a live run on PostgreSQL with the migration job). Every number and output below comes from that run.

---

## 2.1 The brief

Build a service called **`bookmarks`** that stores web links.

### Functional requirements
| # | Requirement |
|---|---|
| F1 | `POST /api/v1/bookmarks` `{url, title}` → **201** with `{id, url, title, created_at}` |
| F2 | URLs are **normalised** before saving: scheme+host lower-cased, fragment dropped, empty path → `/`. `HTTP://Example.COM/a#top` and `http://example.com/a` are **the same bookmark** |
| F3 | Only `http`/`https` URLs with a host are valid → otherwise **422** `BOOKMARKS_INVALID_URL` |
| F4 | A second bookmark with the same normalised URL → **409** `BOOKMARKS_DUPLICATE` (enforced by a database `UNIQUE` constraint, not a racy pre-check) |
| F5 | `GET /api/v1/bookmarks/{id}` → 200, or **404** `BOOKMARKS_NOT_FOUND` |
| F6 | `GET /api/v1/bookmarks?limit=&cursor=` — **cursor pagination** in creation order, each item exactly once; `limit` 1–100 (default 20); bad cursor → 422 |
| F7 | Title: 1–200 characters after trimming whitespace |

### Cross-service requirements (the architecture part)
| # | Requirement |
|---|---|
| C1 | **Contract** `bookmarks_contracts.BookmarksApi` with `get_bookmark(id) -> BookmarkDto` and `count() -> int`; raises `BookmarkNotFound` — *identically* in-process and via the HTTP client |
| C2 | **Event** `bookmarks.bookmark_added.v1` (`bookmark_id`, `url`) written to the **outbox in the same transaction** as the bookmark |
| C3 | **Internal routes** `/internal/v1/bookmarks/{id}` and `/count` (service principals only) mirroring the contract |
| C4 | **Metric** `bookmarks.added` with attribute `outcome ∈ {created, duplicate}` (closed set) |
| C5 | **Database**: your own table in the `bookmarks` schema created by **migration `0002`** (never `create_all` in production) |
| C6 | **Rules**: `make lint` (incl. architecture contracts), `make typecheck` and the service's tests pass **in isolation** |
| C7 | **Docs**: fill in the service README (owner, owns, depends-on) and add a runbook paragraph for what to do if duplicates spike |

### Out of scope
Authentication (Phase C), deleting/updating bookmarks, tags. (See stretch goals.)

## 2.2 Milestones (do them in order — each ends with a command)

| M | Build | Done when |
|---|---|---|
| **M0** | `make new-service name=bookmarks`, `make install`, run its sample tests | `uv run pytest services/bookmarks/service -q` → green |
| **M1** | **Domain**: `Bookmark` dataclass, `normalize_url`, three errors (`InvalidUrlError`, `BookmarkDuplicateError`, `BookmarkNotFoundError`) — pure Python | a parametrised unit test for F2/F3 passes with **no** framework imports (`lint-imports` ✅) |
| **M2** | **Persistence**: table in `models.py`, migration `0002`, repository (`add/get/list_page/count`), `UnitOfWork.bookmarks` | migration renders valid SQL: `BOOKMARKS_DATABASE_URL=postgresql+asyncpg://b:b@localhost/db uv run alembic -c services/bookmarks/service/migrations/alembic.ini upgrade head --sql` |
| **M3** | **Use cases**: `AddBookmark`, `GetBookmark`, `ListBookmarks`, `CountBookmarks` (+ outbox event + metric) | use-case tests with the real SQLite unit of work pass |
| **M4** | **HTTP**: schemas, routes, dependencies; domain errors mapped by the platform | `curl` examples below behave as shown |
| **M5** | **Contract**: DTO, `BookmarksApi` methods, in-process impl (translate domain→contract errors), HTTP client methods, internal routes | **one** contract test file runs green for **both** implementations |
| **M6** | **Run it for real**: `APP_PORT=18000 make up`, exercise the API, inspect the database and outbox | acceptance output (§2.4) matches |
| **M7** | **Docs + cleanup**: README, runbook paragraph, `make docs-check`, remove anything you added only for experiments | `make lint typecheck test docs-check` all green |

## 2.3 Hints (open only when stuck — in order of spoilers)

<details><summary>Hint 1 — design (no code)</summary>

- Put **every rule you can** in `domain/`; the use case should just orchestrate: *normalise → build entity → open UoW → add → add event → commit*.
- Let the **database** decide uniqueness (`UNIQUE (url)`), and translate `IntegrityError` into your domain error inside the repository. A "check then insert" has a race.
- Because ids come from `uuid7()` (time-ordered, strictly increasing), **keyset pagination** is simply `WHERE id > :cursor ORDER BY id LIMIT n+1` — fetch one extra row to know whether a next page exists. No `OFFSET`.
- The contract's in-process implementation must **catch the domain error and raise the contract error** (rule C-4).
- In the contract test, **resolve `BookmarksApi` from the container** (`app.state.container.resolve(BookmarksApi)`) instead of constructing the implementation by hand — that's what keeps the test valid when constructors change (the scaffold now does this too).
</details>

<details><summary>Hint 2 — the domain rule (spoiler)</summary>

```python
def normalize_url(raw: str) -> str:
    parts = urlsplit(raw.strip())
    try:
        port = parts.port
    except ValueError as exc:
        raise InvalidUrlError() from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise InvalidUrlError()
    netloc = parts.hostname.lower() + (f":{port}" if port else "")
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))   # fragment dropped
```
Test inputs worth covering: `"HTTP://Example.COM/a#top"`, `"  https://example.com  "`, `"https://Example.com:8443/x?q=1"`, and rejects: `""`, `"not a url"`, `"ftp://example.com"`, `"https://"`, `"javascript:alert(1)"`, `"http://x:99999999"` (invalid port!).
</details>

<details><summary>Hint 3 — persistence (spoiler)</summary>

```python
# models.py
bookmarks_table = Table("bookmarks", metadata,
    Column("id", Uuid, primary_key=True), Column("url", String(2048), nullable=False),
    Column("title", String(200), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("url", name="uq_bookmarks_url"))

# repository.py
async def add(self, bookmark):
    try:
        await self._session.execute(insert(self._t).values(...))
    except IntegrityError as exc:
        raise BookmarkDuplicateError() from exc

# migrations/versions/0002_bookmarks.py   (a frozen snapshot — never import app code)
revision, down_revision = "0002", "0001"
op.create_table("bookmarks", sa.Column("id", sa.Uuid(), nullable=False), ...,
                sa.PrimaryKeyConstraint("id", name="pk_bookmarks"),
                sa.UniqueConstraint("url", name="uq_bookmarks_url"), schema="bookmarks")
```
Don't forget: the `UnitOfWork` protocol in `application/ports.py` needs a read-only `bookmarks` property so mypy accepts `SqlUnitOfWork` (see [A1·08 §8.2](../phase-a1/08-quality-gates-and-ci.md)).
</details>

<details><summary>Hint 4 — the use case (spoiler)</summary>

```python
@traced_use_case
async def __call__(self, url: str, title: str) -> Bookmark:
    bookmark = Bookmark(id=uuid7(), url=normalize_url(url), title=title.strip(), created_at=self._clock.now())
    try:
        async with self._uow_factory() as uow:
            await uow.bookmarks.add(bookmark)                                         # may raise BookmarkDuplicateError
            await uow.outbox.add(BookmarkAdded(bookmark_id=bookmark.id, url=bookmark.url))   # SAME transaction
            await uow.commit()
    except BookmarkDuplicateError:
        BOOKMARKS_ADDED.add(outcome="duplicate"); raise
    BOOKMARKS_ADDED.add(outcome="created")
    return bookmark
```
The metric lives in `application/telemetry.py` with `allowed={"outcome": frozenset({"created", "duplicate"})}`.
</details>

<details><summary>Hint 5 — the pitfalls we hit while building the reference</summary>

1. **Tests passed but production would have failed**: unit tests use `metadata.create_all`, so a missing/incorrect **migration** is invisible until you run on Postgres (M6).
2. The generated sample contract test **hand-constructed** the implementation → broke when the constructor changed. Resolve from the container.
3. Forgetting that **IDs are not auto-increment**: pass `uuid7()` yourself (rule D-9).
4. Using `OFFSET` pagination → duplicates/gaps when rows are inserted between pages. Use the cursor.
5. Putting `HTTPException` or FastAPI imports in the use case → `lint-imports` fails (L-2/L-3).
6. Adding a metric attribute like `url` → `MetricAttributeError` locally (closed sets, rule O-5).
</details>

## 2.4 Acceptance: what "correct" looks like

Run `APP_PORT=18000 make up`, then (real output from the reference solution):

```bash
curl -i -X POST localhost:18000/api/v1/bookmarks -H 'content-type: application/json' \
     -d '{"url":"HTTPS://Example.COM/Docs#intro","title":" FastAPI docs "}'
```
```
HTTP/1.1 201 Created
{"id":"01a152ff-01ca-74cb-810f-bbdbc968f3b6","url":"https://example.com/Docs","title":"FastAPI docs","created_at":"2026-10-19T07:10:06.282495Z"}
```
```
duplicate (same URL once normalised) → HTTP/1.1 409 Conflict
{"error":{"code":"BOOKMARKS_DUPLICATE","message":"This URL is already bookmarked.","details":{},"request_id":"01a152ff-01f1-7531-…"}}

ftp://x → HTTP/1.1 422 Unprocessable Entity
{"error":{"code":"BOOKMARKS_INVALID_URL","message":"The URL must be a valid http(s) address.", …}}

GET /api/v1/bookmarks?limit=2 → ['https://example.com/Docs', 'https://site1.test/']  next_cursor set: True
```
In the database (`docker compose exec postgres psql -U postgres -d befastapi`):
```
tables in schema bookmarks:  alembic_version, bookmarks, outbox
5 bookmarks rows; alembic 0002
5 events published, 0 pending            ← the relay delivered every event
```
Quality gates:
```
make lint                 → Contracts: 5 kept, 0 broken     (your service's 2 + the shared 3)
make typecheck            → Success: no issues found
uv run --isolated --package bookmarks-service pytest services/bookmarks/service -q   → 24 passed (reference)
make docs-check           → OK
```
Remove your experiment when done: `make down`, then delete `services/bookmarks apps/bookmarks_api` and run `make sync`.

## 2.5 Rubric (self- or mentor-assessed; 0–3 each, 36 max)

| Criterion | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **Correctness** (F1–F7) | many fail | core path works | all functional reqs | + edge cases (bad port, race on duplicates) |
| **Boundaries** (rules B/L) | gates fail | passes with waivers | gates green | clean ports/adapters, no accidental coupling |
| **Data** (D-rules, migration) | `create_all` only | migration exists, untested | migration verified on Postgres | + unique constraint is the source of truth, additive and reversible |
| **Events** (D-5, C-6/7) | none | published directly | outbox in same transaction | + test proving atomicity & idempotent handling |
| **Contract** (C1/C-4) | missing | one implementation | both implementations | + same errors/assertions via one shared test |
| **Tests** | few | happy path | unhappy paths too | + failing-test-first for each bug found |
| **Observability** | none | logs only | metric w/ closed set | + span names reviewed, runbook paragraph |
| **Errors** | raw 500s | inconsistent | uniform body, stable codes | + request_id verified end to end |
| **Docs** | none | README stub | README + runbook | + `docs-check` green, troubleshooting entry for anything surprising |
| **Quality gates** | red | green locally | green + isolated tests | + scaffold-check unaffected |
| **Real-stack proof** | not run | ran, didn't verify | verified API + DB + outbox | + trace/log/metric found for one request |
| **Communication** | — | PR without context | PR with why/how | + checklist ticked honestly, trade-offs noted |

**Passing:** 24+. **Strong:** 30+. Discuss every ≤1 with your mentor.

## 2.6 Stretch goals
1. `DELETE /api/v1/bookmarks/{id}` + event `bookmarks.bookmark_removed.v1` (what status for deleting twice? Document it.)
2. `GET /api/v1/bookmarks?q=` substring search with an index (prove with `EXPLAIN` on Postgres).
3. A Grafana dashboard JSON in `services/bookmarks/observability/dashboards/` showing `bookmarks_added_total` by outcome (`make obs-sync`, then find it under *Services*).
4. A second service `readinglist` that needs `BookmarksApi.get_bookmark` — build the **port + adapter + wiring** (no imports of `bookmarks_service`!) and a test with a fake.

## 🎯 Interview Questions (about the capstone)
1. **Why is the unique constraint the source of truth for duplicates?** *A pre-check is racy: two requests can both pass it. The database serialises the conflict and we translate its error.*
2. **Why must the event and the row commit together?** *Otherwise a crash between them either loses the event or announces something that doesn't exist.*
3. **How would you prove your contract is identical in-process and over HTTP?** *One parametrised test fixture yielding both implementations; the same assertions run twice.*
4. **How did you verify the migration?** *Rendered offline SQL, then ran the job on real Postgres and inspected the schema.*

## ✅ Self-check
- [ ] M0–M7 done; acceptance output matches.
- [ ] I scored 24+ on the rubric and can defend every ≤1.
- [ ] I removed experimental code and the generated service when finished.

**Next:** [Assessment · 03 — Skills matrix →](03-skills-matrix.md)
