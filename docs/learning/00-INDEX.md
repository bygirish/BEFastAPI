# BEFastAPI — Learning & Onboarding Guide

> **Who this is for:** a developer who knows basic Python and has heard of REST APIs, but has **not** built a
> multi-service backend before. No prior knowledge of FastAPI internals, packaging, observability or
> architecture patterns is assumed — every term is explained the first time it appears (and in the [glossary](glossary.md)).
>
> **Why it exists:** each project phase ships working code **and** a chapter here. After reading a phase you should be able to
> (1) explain *why* it was built that way, (2) run and modify it, and (3) review someone else's change to it.

---

## How to read this (pick a path)

| Path | For | What to do | Time |
|---|---|---|---|
| 🎓 **Study path** | Learning the ideas properly | Read the chapters in order, run every ▶ **Try it** block, attempt the labs, then answer the 🎯 interview questions *without scrolling* | ~1–2 days |
| 🚀 **KT / onboarding path** | New joiner who must contribute this week | [Chapter 01](phase-a1/01-the-big-picture.md) → [03](phase-a1/03-boundaries-contracts-and-layers.md) → [05](phase-a1/05-a-request-end-to-end.md) → [07 hands-on](phase-a1/07-adding-a-service-hands-on.md), then keep the [cheat-sheet](cheatsheet.md) open | ~half a day |
| 🔎 **Reference path** | You know the ideas, need a fact | [Cheat-sheet](cheatsheet.md), [glossary](glossary.md), [troubleshooting](troubleshooting.md), and the formal specs in [`docs/architecture/`](../architecture/README.md) | minutes |

Two-pass advice: read once for **understanding** (skip the 🎯 blocks), then a second time for **expertise**
(do the 🎯 blocks and the labs).

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

## Phase A1 — Foundation (what exists today)

The project is a **modular monolith**: one deployable app made of independent *services* (Auth, Users, Files,
Notifications …) that are separated so strictly that any one of them can later be lifted into its own repo in about a day or two.
Phase A1 builds the **foundation** all services will stand on.

| # | Chapter | You will learn |
|---|---|---|
| 01 | [The big picture](phase-a1/01-the-big-picture.md) | Monolith vs microservices vs *modular* monolith; the repo map; the one rule |
| 02 | [Monorepo & uv](phase-a1/02-monorepo-and-uv.md) | Python packages, `pyproject.toml`, virtualenvs, uv workspaces, entry points, lockfiles |
| 03 | [Boundaries, contracts & layers](phase-a1/03-boundaries-contracts-and-layers.md) | What a *contract* is, ports & adapters, layering, how a tool *enforces* architecture |
| 04 | [Platform libraries tour](phase-a1/04-platform-libraries-tour.md) | The five shared libraries with runnable mini-examples (IDs, errors, DI, JWT, redaction…) |
| 05 | [A request, end to end](phase-a1/05-a-request-end-to-end.md) | Follow one HTTP call through every layer, including the outbox + event bus (real logs/spans) |
| 06 | [Observability for beginners](phase-a1/06-observability-for-beginners.md) | Logs vs metrics vs traces; correlation; the double-counting bug we found |
| 07 | [Adding a service (hands-on)](phase-a1/07-adding-a-service-hands-on.md) | Generate a service, read it, extend it, break a rule on purpose |
| 08 | [Quality gates & CI](phase-a1/08-quality-gates-and-ci.md) | ruff, mypy, import-linter, pytest, the scaffold check, reading failures |

Supporting pages: [Glossary](glossary.md) · [Cheat-sheet](cheatsheet.md) · [Troubleshooting (real errors we hit)](troubleshooting.md)

## Upcoming phases (chapters are added as each phase lands)

| Phase | Chapter(s) planned |
|---|---|
| A2 – Local environment & observability stack | Docker & Compose for beginners; running Grafana/Tempo/Loki/Prometheus; reading your first trace |
| B – Notifications | Vendor-neutral facade (adapter pattern in anger); static OTP for tests |
| C – Auth | Passwords & hashing, JWT/JWKS deep-dive, OTP flows, lockout, RBAC with organizations |
| D / E – Users, Files | Event-driven read models; signed URLs & storage ports |
| F – Split rehearsal | Extracting a service for real (the playbook, step by step) |

## Where the "official" rules live

These chapters **teach**; the files in [`docs/architecture/`](../architecture/README.md) **decide**. If they ever disagree, the
architecture docs win — and please fix the chapter.

| Question | Authoritative doc |
|---|---|
| What are we building and why this shape? | [ARCHITECTURE](../architecture/ARCHITECTURE.md) |
| What must / must not I do in code? (rule IDs like `B-1`, `L-4`) | [STANDARDS](../architecture/STANDARDS.md) |
| How do logs/metrics/traces work here? | [OBSERVABILITY](../architecture/OBSERVABILITY.md) |
| How do we run everything locally? | [LOCAL_ENVIRONMENT](../architecture/LOCAL_ENVIRONMENT.md) |
| How do we split a service out later? | [EXTRACTION_PLAYBOOK](../architecture/EXTRACTION_PLAYBOOK.md) |
| What is Auth going to do? | [Auth plan](../../services/auth/docs/PLAN.md) |

## Keeping this guide alive (for maintainers)

Documentation is part of the **Definition of Done** for every phase: no phase is "done" until its chapter(s) exist, every ▶ block
was actually run, and links were checked. Use [`templates/chapter-template.md`](templates/chapter-template.md).
