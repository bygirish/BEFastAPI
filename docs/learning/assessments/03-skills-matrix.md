# Assessment · 03 — Skills Matrix

**Goal:** a shared definition of "what good looks like" at each level, so you can see where you are, what to learn next, and when you are ready to review or own a service.
**How to use:** tick what you can do **without help**, in a real task (not just reading). Be honest — the matrix is for *you* and your mentor, not a grade. Re-do it every phase.

> **Levels:** **L1 Learner** — understands and can follow the guide · **L2 Contributor** — ships changes safely with light review · **L3 Reviewer** — spots problems in others' changes · **L4 Owner** — designs and is accountable for a service.

| Area | L1 Learner | L2 Contributor | L3 Reviewer | L4 Owner |
|---|---|---|---|---|
| **Python & async** ([F·01](../foundations/01-python-for-this-codebase.md)) | reads type hints, runs async code | writes typed async code that passes `mypy --strict`; never blocks the loop | spots blocking calls, wrong Pydantic/dataclass choice, bad `Protocol` use | defines typing/async conventions for the service |
| **HTTP & FastAPI** ([F·02](../foundations/02-http-and-fastapi-basics.md)) | explains status codes, runs the demo | adds routes with schemas; uses `Depends` only in `api/` | flags business logic in routers, wrong status codes, leaked ORM models | designs the public API and its evolution (additive changes) |
| **Databases** ([F·03](../foundations/03-databases-for-backend-developers.md)) | explains transactions, indexes | writes a UoW use case + migration; avoids N+1 | catches missing indexes, non-atomic dual writes, non-additive migrations | owns the schema, data ownership and capacity decisions |
| **Testing** ([F·04](../foundations/04-testing-guide.md)) | runs tests, reads failures | writes unit/service/contract tests with fakes | rejects mock-heavy or assertion-free tests; asks for negative tests | owns the test strategy and the extraction-drill readiness |
| **Architecture** ([A1·03](../phase-a1/03-boundaries-contracts-and-layers.md), [KT·03–05](../kt/03-design-patterns-catalog.md)) | explains contract, port/adapter, layers | places code in the right layer; uses ports for other services | applies rule IDs in review (B/L/D/C); spots hidden coupling | proposes/justifies ADRs; decides what to split |
| **Events & messaging** ([A1·05](../phase-a1/05-a-request-end-to-end.md)) | explains the outbox and at-least-once | publishes events via outbox; writes idempotent handlers | finds dual-writes, ordering assumptions, fat events | evolves event schemas safely (versioning) |
| **Observability** ([A1·06](../phase-a1/06-observability-for-beginners.md), [A2·03](../phase-a2/03-the-observability-stack-in-practice.md)) | finds a request's log → trace → metric | adds spans/metrics with closed label sets; no PII in telemetry | spots cardinality bombs, unlogged failure paths | defines SLOs, alerts and runbooks |
| **Containers & local stack** ([A2·01–02](../phase-a2/01-docker-for-beginners.md)) | runs `make up`, reads `compose ps` | adds env/config the right way (E-rules) | spots secrets in images, bad startup ordering | owns the service's Dockerfile and deploy readiness |
| **Debugging** ([KT·06](../kt/06-debugging-playbook.md)) | follows the six-step method with help | diagnoses a failure from a request id alone | teaches the method; improves failure-path logging | leads incident reviews and adds guards/alerts |
| **Security basics** (grows with Phase C) | knows what must never be logged | derives identity from the principal, not the body (X-2) | catches enumeration, unvalidated input, secret leaks | owns threat model and auth design |
| **Process & docs** ([CONTRIBUTING](../../../CONTRIBUTING.md)) | follows the PR checklist | keeps docs, glossary and troubleshooting updated; `docs-check` green | enforces Definition of Done | maintains the guide and the standards |

## Self-assessment procedure (30 min)
1. Print/copy the table; mark each cell ✅ (can do unaided), 🟡 (with help), ❌ (not yet).
2. Your **level** = the highest column where you have ✅ in **most** rows and no ❌ in Architecture, Testing or Debugging.
3. Pick the **two weakest rows**, open the linked chapter, and plan one concrete task for each (e.g., "write a contract test for X", "debug the Postgres-down drill").
4. Show the filled matrix to your mentor; agree one goal for the next phase.

## Evidence that counts (examples)
| Level up to… | Evidence |
|---|---|
| L2 Contributor | the [capstone](02-capstone-project.md) scoring 24+, an accepted PR using the template honestly |
| L3 Reviewer | 5 substantive review comments that cite rule IDs and were accepted; question bank 50+ |
| L4 Owner | an ADR you authored, an SLO/runbook you maintain, an extraction drill you ran against the playbook budget |

## 🎯 Interview Questions
1. **What distinguishes a reviewer from a contributor on this codebase?** *A reviewer sees what is *missing* — an unhappy-path test, an atomicity gap, an unbounded label — and cites the rule, rather than only checking that the code works.*
2. **How do you decide when a service is "ready for ownership"?** *You can explain its data, contract, events, SLOs and failure modes, have run its debugging drills, and kept its docs and alerts current.*

## ✅ Self-check
- [ ] I filled in the matrix honestly and chose my two weakest rows.
- [ ] I have a concrete task for each and a goal agreed with my mentor.

**Back to the [index](../00-INDEX.md).**
