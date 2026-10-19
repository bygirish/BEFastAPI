# KT · 02 — Reading Guide and Onboarding Plan

**Goal:** a concrete plan for a new developer: *which files to read in which order, what to notice in each, and what to build to prove you understood* — from day 1 to the end of week 1.
**Prerequisites:** none (that's the point). **Time:** 1 week part-time.

---

## 2.1 The reading order (the "guided tour")

Read **code with questions**. For each stop, open the file, spend ~10 minutes, then answer the question *before* looking at the notes.

| # | Open | Notice | Question to answer |
|---|---|---|---|
| 1 | [`pyproject.toml`](../../../pyproject.toml) | the workspace `members` block and the `[tool.ruff]`, `[tool.mypy]` sections | Why is there a generated block in a config file? Who writes it? |
| 2 | [`libs/platform_core/src/platform_core/errors.py`](../../../libs/platform_core/src/platform_core/errors.py) | the class hierarchy; nothing mentions HTTP | Where does `NotFoundError` become a `404`? |
| 3 | [`libs/platform_core/src/platform_core/container.py`](../../../libs/platform_core/src/platform_core/container.py) | `bind` / `resolve` keyed by a `Protocol` class | What does `override=True` protect against? |
| 4 | [`libs/platform_http/src/platform_http/module.py`](../../../libs/platform_http/src/platform_http/module.py) | the `ServiceModule` protocol and `BaseServiceModule` defaults | What are the eight things a service can provide to the platform? |
| 5 | [`libs/platform_http/src/platform_http/compose.py`](../../../libs/platform_http/src/platform_http/compose.py) | order of operations in `create_application` | In what order are `provide`, `wiring`, `register_event_handlers`, `on_startup` called? Why that order? |
| 6 | [`libs/platform_observability/src/platform_observability/middleware.py`](../../../libs/platform_observability/src/platform_observability/middleware.py) | request id handling, `app.service` from the URL | Why are health endpoints excluded from the access log? |
| 7 | [`libs/platform_events/src/platform_events/outbox.py`](../../../libs/platform_events/src/platform_events/outbox.py) | `SqlOutboxWriter.add` vs `SqlOutboxStore.drain` | Why are *writing* and *draining* different classes? |
| 8 | [`libs/platform_events/src/platform_events/relay.py`](../../../libs/platform_events/src/platform_events/relay.py) | `run_once`, `_loop`, `stop` | What happens to an event whose handler keeps failing? |
| 9 | [`libs/platform_security/src/platform_security/verifier.py`](../../../libs/platform_security/src/platform_security/verifier.py) | every way a token can be rejected | Why is `none` refused as an algorithm? |
| 10 | [`tools/templates/service`](../../../tools/templates/service) (the generator's output, read via [chapter A1·07](../phase-a1/07-adding-a-service-hands-on.md)) | the layers: `api → application → domain`, `infrastructure` on the side | Which file is the *only* one that imports another service's contracts? |
| 11 | [`docker-compose.yml`](../../../docker-compose.yml) | `depends_on` conditions and the generated blocks | What would happen if `db-provision` failed? |
| 12 | [`deploy/observability/otel-collector/config.yaml`](../../../deploy/observability/otel-collector/config.yaml) | three pipelines, two connectors | Where would you add a second backend for traces? |

> 💡 **Learning Thought — read top-down by dependency, not alphabetically.** `platform_core` has no dependencies; each later stop uses the earlier ones. If a file confuses you, you skipped a stop.

## 2.2 Day-by-day plan

### Day 1 — Get it running and see the shape
- [ ] Read [A1 · 01](../phase-a1/01-the-big-picture.md) and [A1 · 02](../phase-a1/02-monorepo-and-uv.md).
- [ ] `make install`, then `make lint typecheck test` — all green.
- [ ] Generate a service (`make new-service name=notes`), run its tests, look at the tree.
- [ ] **Checkpoint:** explain to a teammate (or rubber duck) what a *contract* is and where it lives.

### Day 2 — Request path and boundaries
- [ ] Read [A1 · 03](../phase-a1/03-boundaries-contracts-and-layers.md) and [A1 · 05](../phase-a1/05-a-request-end-to-end.md); do reading stops 1–8 above.
- [ ] Break an architecture rule on purpose (`import fastapi` in `domain/`), watch `lint-imports` fail, then fix it.
- [ ] **Checkpoint:** draw the sequence diagram of `GET /api/v1/<name>/ping` from memory.

### Day 3 — Run the whole system and *look*
- [ ] Read [A2 · 01–03](../phase-a2/01-docker-for-beginners.md); `cp .env.example .env && make up` (use `APP_PORT=18000` if 8000 is taken).
- [ ] Find your own request in Grafana: Explore → Loki → *Open trace* → *Logs for this span*.
- [ ] Do the drills in the [debugging playbook](06-debugging-playbook.md) (at least drills 1 and 2).
- [ ] **Checkpoint:** from a request id alone, find the log, the trace and the metric.

### Day 4 — Foundations gaps
- [ ] Read whichever of [F · 01–04](../foundations/01-python-for-this-codebase.md) you're least sure of; run every snippet.
- [ ] Read [A1 · 04 platform libraries tour](../phase-a1/04-platform-libraries-tour.md) and [KT · 03 patterns](03-design-patterns-catalog.md).
- [ ] **Checkpoint:** pick any pattern from the catalogue and point to where it lives in the repo.

### Day 5 — Make a change the right way
- [ ] Do [A1 · 07 hands-on](../phase-a1/07-adding-a-service-hands-on.md) (the `shout` feature) end to end, including contract tests.
- [ ] Open a pull request against yourself using the template and tick every box honestly.
- [ ] **Checkpoint:** a reviewer could tell *why* each file changed from the PR description alone.

### Week 1 finish — Capstone
- [ ] Start the [capstone project](../assessments/02-capstone-project.md) and take the [question bank](../assessments/01-question-bank.md) self-test.
- [ ] Fill in the [skills matrix](../assessments/03-skills-matrix.md) and agree next steps with your mentor.

## 2.3 How to learn from this codebase (habits that pay off)

1. **Run before you read.** Seeing `make stack-check` pass makes the code's purpose concrete.
2. **Follow one request** (we give you ids) instead of reading everything.
3. **Change one thing, predict the outcome, run.** Wrong predictions are where the learning is.
4. **Read the tests first** — they are executable documentation of intended behaviour.
5. **Use the rule IDs.** When a check fails, look the ID up in [STANDARDS](../../architecture/STANDARDS.md); every rule has a *why*.
6. **Write down what confused you** and add it to [troubleshooting](../troubleshooting.md) — the next newcomer will thank you.

## 2.4 Who to ask and what to bring

| Situation | Do this first |
|---|---|
| A check fails and you don't know why | Search [troubleshooting](../troubleshooting.md) for the first error line |
| You don't know where code belongs | [Cheat-sheet "Where does this code go?"](../cheatsheet.md) |
| You want to bend an architecture rule | Read [STANDARDS §9 exceptions](../../architecture/STANDARDS.md#9-exceptions-process): an ADR with an owner and an expiry date |
| You found a doc that's wrong | Fix it in the same PR and run `make docs-check` |

## 🎯 Interview Questions
1. **A new service needs data owned by another service. Walk me through the files you touch.** *Port in the consumer's `application/ports.py`; adapter in its `infrastructure/clients/` using the provider's `*_contracts`; binding in `apps/*/wiring.py`; contract + contract tests in the provider if a method is missing.*
2. **You're asked to "just import the other service's model". What do you say?** *No: B-1 forbids it (CI fails); add/extend the provider's contract and call it through a port so the boundary survives extraction.*
3. **How do you find everything that happened for one customer complaint?** *Ask for the `request_id` (shown in every error body), search Loki by it, open the linked trace, check the metric panel for that route.*

## ✅ Self-check
- [ ] I followed the reading order and can answer the question at each stop.
- [ ] I finished the Day-3 checkpoint (request id → log → trace → metric).
- [ ] I know where to look when something fails, before asking.

**Next:** [KT · 03 — Design patterns catalogue →](03-design-patterns-catalog.md)
