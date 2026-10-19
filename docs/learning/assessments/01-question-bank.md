# Assessment · 01 — Question Bank

**Goal:** one place to test yourself on everything in this guide — 60 questions with model answers, grouped by topic, each pointing to the chapter that teaches it.
**How to use:** (1) cover the answers and answer aloud or in writing; (2) mark ✅/❌; (3) re-read the linked chapter for every ❌; (4) repeat in a week. Interviewers and code reviewers ask exactly these kinds of things.

> **Scoring guide:** 50+ ✅ → you can review others' changes; 40–49 → you can contribute independently; 30–39 → keep going through the chapters; < 30 → start with [Foundations](../foundations/01-python-for-this-codebase.md).

---

## A. Python & async  ([F·01](../foundations/01-python-for-this-codebase.md))
1. **Do type hints change how Python runs code?** *No. They're ignored at runtime; mypy checks them before.*
2. **dataclass vs Pydantic?** *Pydantic validates and coerces untrusted input; dataclasses are lightweight and don't validate.*
3. **What does `await` do?** *Suspends the coroutine so the event loop can run other tasks until the awaited operation completes.*
4. **What happens if you call `time.sleep(1)` inside `async def`?** *It blocks the whole event loop — every request stalls for that second.*
5. **What does calling an `async def` function without `await` return?** *A coroutine object that hasn't run.*
6. **Why use `asyncio.gather`?** *To wait on independent operations concurrently (0.2 s instead of 0.6 s for three 0.2 s waits).*
7. **What does a context manager guarantee?** *Cleanup runs even if the body raises.*
8. **What is a decorator, and one use here?** *A function that wraps another to add behaviour; `@traced_use_case` opens a span around a use case.*
9. **Why `Protocol` instead of an abstract base class?** *Structural typing: any object with the right methods fits, so tests can pass tiny fakes.*
10. **What does `def f[T](x: T) -> T` mean?** *A generic function using Python 3.12 syntax: the return type equals the argument type.*

## B. HTTP & FastAPI  ([F·02](../foundations/02-http-and-fastapi-basics.md))
11. **4xx vs 5xx?** *4xx = caller's mistake; 5xx = our failure. Only 5xx counts against our SLO.*
12. **Which methods are safe to retry automatically?** *GET, PUT, DELETE (idempotent); POST only with an idempotency key.*
13. **Where do validation errors come from in FastAPI?** *Declared types/constraints (Pydantic); FastAPI returns 422 automatically.*
14. **What does `Depends` do, and where may we use it?** *Declares/injects per-request dependencies; only in `api/` (rule L-6).*
15. **What is ASGI?** *The async interface between a server (uvicorn) and the app: `await app(scope, receive, send)`.*
16. **Why are our routes "thin"?** *Parse → one use case → return; logic in the application layer so jobs/handlers can reuse it (L-4).*
17. **Why don't use cases raise `HTTPException`?** *It welds business logic to HTTP; they raise domain errors the HTTP edge maps.*
18. **How do you test a FastAPI app without a server?** *`httpx.AsyncClient(transport=ASGITransport(app=app))`.*

## C. Databases  ([F·03](../foundations/03-databases-for-backend-developers.md))
19. **Explain ACID.** *Atomic, Consistent, Isolated, Durable — e.g., a bank transfer's two updates commit or neither does.*
20. **What does an index cost?** *Slower writes and extra space; add them for columns you filter/join/sort by.*
21. **What is N+1?** *One query for a list plus one per item; fix with a join or batch query.*
22. **`FOR UPDATE SKIP LOCKED` — why?** *Concurrent workers each claim different rows without waiting or double-processing.*
23. **Why schema-per-service?** *Data ownership enforced by the database, easy extraction (dump + new URL).*
24. **What is a unit of work?** *One transaction scope per use case: commit on success, rollback on exception.*
25. **Why must migrations not import application code?** *Application code evolves; a migration must always reproduce the same change.*
26. **A migration job exits 0 but the table is missing. Why?** *A transaction was never committed (Alembic given an already-open transaction) — verify results, not exit codes.* ([A2·02](../phase-a2/02-compose-the-whole-system.md))

## D. Testing  ([F·04](../foundations/04-testing-guide.md))
27. **Fake vs mock?** *A fake is a working stand-in you assert outcomes against; a mock records calls. Prefer fakes.*
28. **What does `parametrize` give you?** *One test body over many inputs, reported separately.*
29. **Why isn't 100 % coverage proof of correctness?** *Coverage shows what ran, not what was asserted.*
30. **How do you test time-dependent code?** *Inject a clock (`FixedClock`) and advance it.*
31. **Why test each package in an isolated environment?** *To prove it declares all its own dependencies (B-6).*
32. **What is a contract test here?** *The same assertions run against the in-process implementation and the HTTP client.*
33. **Why start a bug fix with a failing test?** *It proves you reproduced the bug and guards against regression.*

## E. Architecture  ([A1·01–03](../phase-a1/01-the-big-picture.md), [KT·03–05](../kt/03-design-patterns-catalog.md))
34. **What is a modular monolith and why choose it first?** *One deployable with enforced module boundaries; cheap to run now, extractable later.*
35. **What is "the one rule"?** *Design every service as if remote; deploy them as one process.*
36. **What may one service import from another?** *Only its `*_contracts` package (B-1).*
37. **Port vs adapter?** *A port is the interface the consumer owns; an adapter plugs it into something real.*
38. **Name the layers and the import direction.** *api → application → domain; infrastructure plugs into application ports; never the reverse (L-1).*
39. **Why four different "models" (HTTP, domain, ORM, DTO)?** *So a change in one (table column) doesn't leak into the others (public API).*
40. **What is the transactional outbox solving?** *The dual-write problem: saving data and publishing an event atomically.*
41. **What delivery guarantee do events have and what does it require?** *At-least-once; idempotent handlers.*
42. **What is the composition root?** *The single place (`apps/*`) that assembles services and binds ports to providers.*
43. **Why is `service/` a sibling of `contracts/`?** *uv forbids nested workspace members, and it makes public/private visible.*
44. **How does extraction work?** *Move the folder, change one binding to an HTTP client, move one schema (see the playbook).*
45. **How do we stop people breaking boundaries?** *import-linter in CI, generated per service, plus isolated per-package tests.*

## F. Observability  ([A1·06](../phase-a1/06-observability-for-beginners.md), [A2·03](../phase-a2/03-the-observability-stack-in-practice.md))
46. **Logs vs metrics vs traces?** *Metrics detect, traces localise, logs explain; link them with a trace id.*
47. **What is cardinality and why care?** *Distinct label combinations; unbounded labels (ids, URLs) explode storage.*
48. **What is an exemplar?** *A sample trace id on a metric point; jump from a slow bucket to a trace.*
49. **What is `app.service` for?** *A logical-service label on every signal so dashboards survive extraction.*
50. **Why a Collector between app and backends?** *One protocol out of the app; backends, sampling and redaction become configuration.*
51. **Explain burn-rate alerting.** *Alert on the speed of error-budget consumption using a long and a short window; fast burns page, slow burns ticket.*
52. **Why must logging code never raise?** *It runs inline in request code; a handler bug becomes a request/start-up failure.*
53. **Why `X-Request-ID` in every error body?** *So users can quote it and you can find the exact log/trace.*
54. **Why is telemetry best-effort?** *Losing telemetry is cheaper than failing customers; logs also go to stdout.*

## G. Containers & delivery  ([A2·01–02](../phase-a2/01-docker-for-beginners.md))
55. **Image vs container?** *Immutable template vs running instance.*
56. **Why multi-stage builds and a non-root user?** *Smaller, safer images; limits blast radius.*
57. **`depends_on` with `condition`?** *Wait for health or successful completion, never for time.*
58. **Why a `db-provision` job instead of init scripts?** *Init scripts run only on first volume creation; the job is idempotent on every `up`.*
59. **Compose vs Kubernetes?** *Compose: containers on one machine (dev/CI); Kubernetes: scheduling, scaling and self-healing across a cluster.*
60. **Why run the real stack even when unit tests pass?** *It finds assembly problems unit tests can't — we found ten ([A2·04](../phase-a2/04-what-the-live-run-taught-us.md)).*

## H. Scenario questions (discuss, don't just recite)
- **S1.** *A user reports an intermittent 500 at 14:03. Walk through your first five minutes.* → request id → Loki → trace → RED dashboard for that route → was it one request or many? ([KT·06](../kt/06-debugging-playbook.md))
- **S2.** *Users service needs the avatar URL from Files. Which files do you touch and what do you not touch?* → port in Users; adapter importing `files_contracts`; binding in `apps/*`; **not** Files' internals or tables.
- **S3.** *Your handler for `auth.user_registered.v1` sometimes creates duplicate profiles. Why, and what's the fix?* → at-least-once delivery; wrap in `idempotent(...)` and make the insert idempotent (unique constraint).
- **S4.** *Your PR adds `from files_service.domain import X` in Users. What happens and what do you do instead?* → `lint-imports` fails (B-1); expose via `files_contracts` and a port.
- **S5.** *The p95 panel looks wrong (a 700 ms request shows as ~975 ms). Bug?* → No: histogram percentiles interpolate within buckets; precision is set by bucket bounds.
- **S6.** *The migration job succeeded but the app says "relation does not exist".* → uncommitted transaction in `env.py`; check the table, not the exit code.
- **S7.** *You want to add a metric label `user_id`. Response?* → No: unbounded cardinality; put ids on traces/logs, labels from closed sets (O-5).

## ✅ Self-check
- [ ] I scored 40+ and re-read the chapters for every miss.
- [ ] I can answer S1–S7 out loud without notes.

**Next:** [Assessment · 02 — Capstone project →](02-capstone-project.md)
