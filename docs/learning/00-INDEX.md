# BEFastAPI — Learning & Onboarding Guide

> **Who this is for:** a developer who knows basic Python and has heard of REST APIs, but has **not** built a
> multi-service backend before. No prior knowledge of FastAPI internals, packaging, databases, observability or
> architecture patterns is assumed — every term is explained the first time it appears (and in the [glossary](glossary.md)).
>
> **Why it exists:** each project phase ships working code **and** documentation. After reading you should be able to
> (1) explain *why* it was built that way, (2) run and modify it, and (3) review someone else's change to it.

**Everything in this guide is verified:** commands were run and outputs pasted from reality; links, anchors and file paths are checked by `make docs-check`.

---

## Start here: pick your path

| You are… | Do this | Time |
|---|---|---|
| 🌱 **New to backend development** | [Foundations F·01–04](#foundations--the-skills-underneath-everything) → [Phase A1](#phase-a1--foundation) → [Phase A2](#phase-a2--local-environment--observability-stack) → [KT pack](#kt-pack--project-knowledge-transfer) → [capstone](assessments/02-capstone-project.md) | ~1–2 weeks part-time |
| 🚀 **Joining the project this week** | [KT·02 onboarding plan](kt/02-reading-guide-and-onboarding-plan.md) (day-by-day), then [KT·01 codebase map](kt/01-codebase-map.md) and the [cheat-sheet](cheatsheet.md) | 1 day to productive, 1 week to confident |
| 🔧 **Experienced, need the facts** | [Cheat-sheet](cheatsheet.md) · [glossary](glossary.md) · [troubleshooting](troubleshooting.md) · [decision log](kt/05-decision-log-in-plain-english.md) · formal specs in [`docs/architecture/`](../architecture/README.md) | minutes |
| 🧭 **Reviewing / owning a service** | [Design patterns](kt/03-design-patterns-catalog.md) · [diagrams](kt/04-architecture-diagrams.md) · [debugging playbook](kt/06-debugging-playbook.md) · [skills matrix](assessments/03-skills-matrix.md) | half a day |
| 🎓 **Teaching others** | [Question bank](assessments/01-question-bank.md) · [capstone with rubric](assessments/02-capstone-project.md) · [chapter template](templates/chapter-template.md) | — |

**Two-pass advice:** read once for **understanding** (skip the 🎯 blocks), then again for **expertise** (do the 🎯 blocks and labs).

## Symbols used in every chapter

| Symbol | Meaning |
|---|---|
| 💡 **Learning Thought** | The durable insight — the thing worth remembering after the details fade |
| ⚠️ **Trap** | A mistake beginners (and we) actually made; usually with the real error message |
| ▶ **Try it** | A command or snippet you can run; the output shown was captured from this repo |
| 🧪 **Lab** | A small exercise (solutions are folded under `<details>`) |
| 🎯 **Interview Questions** | Model answers — also a great self-test for code reviews |
| ✅ **Self-check** | If you can't tick these, re-read the chapter |
| 📚 **Further reading** | External links (checked when written) |

---

## Foundations — the skills underneath everything

*Skip any chapter you already know well; each ends with a self-check so you can tell.*

| # | Chapter | You will learn |
|---|---|---|
| F·01 | [The Python you need](foundations/01-python-for-this-codebase.md) | Type hints, `Protocol`, dataclass vs Pydantic, `async`/`await` (and how to block the loop), context managers, decorators, generics |
| F·02 | [HTTP and FastAPI basics](foundations/02-http-and-fastapi-basics.md) | Requests/responses/status codes, routes, validation, `Depends`, middleware, lifespan, ASGI — with a runnable app |
| F·03 | [Databases for backend developers](foundations/03-databases-for-backend-developers.md) | Transactions (ACID), indexes, N+1, `SKIP LOCKED`, schemas/roles, migrations, SQLAlchemy sessions |
| F·04 | [Testing guide](foundations/04-testing-guide.md) | pytest, async tests, fixtures, fakes vs mocks, the test pyramid, coverage, how to test each kind of code here |

## Phase A1 — Foundation

The project is a **modular monolith**: one deployable app made of independent *services* (Auth, Users, Files, Notifications …) separated so strictly that any one can be lifted into its own repo in about a day or two. Phase A1 builds the foundation they stand on.

| # | Chapter | You will learn |
|---|---|---|
| 01 | [The big picture](phase-a1/01-the-big-picture.md) | Monolith vs microservices vs *modular* monolith; the repo map; the one rule |
| 02 | [Monorepo & uv](phase-a1/02-monorepo-and-uv.md) | Python packages, `pyproject.toml`, virtualenvs, uv workspaces, entry points, lockfiles |
| 03 | [Boundaries, contracts & layers](phase-a1/03-boundaries-contracts-and-layers.md) | What a *contract* is, ports & adapters, layering, how a tool *enforces* architecture |
| 04 | [Platform libraries tour](phase-a1/04-platform-libraries-tour.md) | The five shared libraries with runnable mini-examples |
| 05 | [A request, end to end](phase-a1/05-a-request-end-to-end.md) | One HTTP call through every layer, including the outbox + event bus |
| 06 | [Observability for beginners](phase-a1/06-observability-for-beginners.md) | Logs vs metrics vs traces; correlation; the double-counting bug |
| 07 | [Adding a service (hands-on)](phase-a1/07-adding-a-service-hands-on.md) | Generate a service, extend it, break a rule on purpose |
| 08 | [Quality gates & CI](phase-a1/08-quality-gates-and-ci.md) | ruff, mypy, import-linter, pytest, the scaffold check, reading failures |

## Phase A2 — Local environment & observability stack

`docker compose up` runs **everything**: PostgreSQL, Redis, one migration job per service, the application, and a full observability stack (OpenTelemetry Collector, Tempo, Loki, Prometheus, Alertmanager, Grafana) plus developer tools — and a smoke test proves logs, traces and metrics are correlated.

| # | Chapter | You will learn |
|---|---|---|
| 01 | [Docker for beginners](phase-a2/01-docker-for-beginners.md) | Images vs containers, our multi-stage Dockerfile line by line, non-root, healthchecks |
| 02 | [Docker Compose: the whole system](phase-a2/02-compose-the-whole-system.md) | Profiles, startup order by conditions, one schema per service, migration jobs, generated blocks |
| 03 | [The observability stack in practice](phase-a2/03-the-observability-stack-in-practice.md) | Log → trace → metric → exemplar → dashboard → SLO alert; collector config |
| 04 | [What the live run taught us](phase-a2/04-what-the-live-run-taught-us.md) | Ten real failures found only by running the real system |

## KT pack — project knowledge transfer

| # | Page | Use it to… |
|---|---|---|
| KT·01 | [Codebase map](kt/01-codebase-map.md) | find what every folder/file is for (paths are CI-checked) |
| KT·02 | [Reading guide & onboarding plan](kt/02-reading-guide-and-onboarding-plan.md) | read the code in the right order; follow a day-by-day plan |
| KT·03 | [Design patterns catalogue](kt/03-design-patterns-catalog.md) | name the 16 patterns used here, see where, and when *not* to use them |
| KT·04 | [Architecture diagrams](kt/04-architecture-diagrams.md) | explain the system in pictures (context, containers, components, sequences, data ownership, extraction) |
| KT·05 | [Decision log in plain English](kt/05-decision-log-in-plain-english.md) | learn *why* — 20 decisions, rejected alternatives, trade-offs |
| KT·06 | [Debugging playbook](kt/06-debugging-playbook.md) | diagnose problems with a six-step method and five live drills |
| KT·07 | [Roadmap & pre-reading](kt/07-roadmap-and-prereading.md) | prepare for the next phases |

## Assessments — check what you learned

| # | Page | What it gives you |
|---|---|---|
| 01 | [Question bank](assessments/01-question-bank.md) | 60 questions with answers + 7 scenarios, grouped by topic |
| 02 | [Capstone project: Bookmarks service](assessments/02-capstone-project.md) | a full end-to-end build, milestones, acceptance output, hints, rubric |
| 03 | [Skills matrix](assessments/03-skills-matrix.md) | four levels × eleven skill areas; honest self-assessment |

## Supporting pages

[Glossary](glossary.md) · [Cheat-sheet](cheatsheet.md) · [Troubleshooting — real errors we hit](troubleshooting.md) · [CONTRIBUTING](../../CONTRIBUTING.md) · [Chapter template](templates/chapter-template.md)

## Upcoming phases (chapters are added as each phase lands)

See [KT·07 Roadmap & pre-reading](kt/07-roadmap-and-prereading.md) for what is built next (Notifications → Auth + RBAC → Users → Files → split rehearsal) and what to read beforehand.

## Where the "official" rules live

These chapters **teach**; the files in [`docs/architecture/`](../architecture/README.md) **decide**. If they ever disagree, the architecture docs win — and please fix the chapter.

| Question | Authoritative doc |
|---|---|
| What are we building and why this shape? | [ARCHITECTURE](../architecture/ARCHITECTURE.md) |
| What must / must not I do in code? (rule IDs like `B-1`, `L-4`) | [STANDARDS](../architecture/STANDARDS.md) |
| How do logs/metrics/traces work here? | [OBSERVABILITY](../architecture/OBSERVABILITY.md) |
| How do we run everything locally? | [LOCAL_ENVIRONMENT](../architecture/LOCAL_ENVIRONMENT.md) |
| How do we split a service out later? | [EXTRACTION_PLAYBOOK](../architecture/EXTRACTION_PLAYBOOK.md) |
| What is Auth going to do? | [Auth plan](../../services/auth/docs/PLAN.md) |

## Keeping this guide alive (for maintainers)

Documentation is part of the **Definition of Done** for every phase: no phase is "done" until its chapters exist, every ▶ block was actually run, and `make docs-check` is green
(it fails on broken links/anchors, paths in the codebase map that no longer exist, pages not linked from this index, and chapters missing their standard sections).
Use [`templates/chapter-template.md`](templates/chapter-template.md).
