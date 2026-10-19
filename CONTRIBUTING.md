# Contributing

Welcome! This page is the shortest path from "I cloned the repo" to "my change is merged". For the *why* behind the rules, see the
[learning guide](docs/learning/00-INDEX.md); for the rules themselves, [STANDARDS](docs/architecture/STANDARDS.md).

## 1. One-time setup

```bash
# prerequisites: Python 3.12, uv (https://docs.astral.sh/uv/), and optionally Docker Desktop for the full stack
make install                 # creates .venv and installs every workspace package + dev tools
make lint typecheck test     # everything should be green before you change anything
cp .env.example .env         # only needed to run the Docker stack
```
New here? Follow the [onboarding plan](docs/learning/kt/02-reading-guide-and-onboarding-plan.md).

## 2. The daily loop

```bash
git switch -c <type>/<short-description>     # e.g. feat/bookmarks-service, fix/relay-backoff, docs/testing-guide
# ... make your change (tests first for bugs) ...
make format                  # auto-fix style
make lint typecheck test docs-check          # the same gates CI runs
git add -p && git commit     # small, focused commits
```
| Command | When |
|---|---|
| `make new-service name=<n>` | scaffold a service (never copy another service by hand) |
| `make sync` | after adding/removing a service (regenerates workspace, `.importlinter`, compose blocks) |
| `make test-service s=<n>-service p=services/<n>/service` | one service, only its own dependencies installed |
| `APP_PORT=18000 make up` / `make down` / `make reset` | run / stop / wipe the local stack (needs Docker) |
| `make stack-check` | boot everything with a throw-away service and verify log → trace → metric correlation |
| `make scaffold-check` | prove the service generator still produces a green service |

## 3. Branches and commits

- **Branches:** `feat/…`, `fix/…`, `docs/…`, `chore/…`, `refactor/…` — lowercase, hyphenated.
- **Commit messages:** `type(scope): imperative summary` (≤ 72 chars), a blank line, then a body explaining **why** (what problem, what alternatives). Example:
  `fix(observability): stop double-counting request metrics; use FastAPI native tracing`.
- **One logical change per commit.** Generated files (`.importlinter`, `uv.lock`, compose blocks, `provision.sql`) go in the same commit as the change that caused them.
- **Never commit** secrets, `.env`, or build output (`.gitignore` covers the usual suspects — if `git status` shows something odd, ask).

## 4. Pull requests

1. Fill in the [PR template](.github/pull_request_template.md) **honestly** — each box refers to a rule ID.
2. Explain *why*, not just *what*; link the issue/ADR; paste test evidence (commands run, trace link for behaviour changes).
3. Keep it reviewable: aim for a diff someone can understand in 15 minutes. Split refactors from behaviour changes.
4. CI must be green: static (ruff, mypy, import-linter, generated files, docs), one test job **per package** (each in isolation), and the scaffold check.
5. Respond to review comments with commits (not force-pushes) until approved.

## 5. Definition of Done

A change is done when **all** of these hold:

- [ ] Behaviour is covered by tests, including the unhappy path (bug fixes start with a failing test).
- [ ] `make lint typecheck test docs-check` is green; architecture rules weren't waived (or an ADR with an owner and an **expiry date** exists).
- [ ] Anything that crosses a service boundary goes through a contract + port/adapter; cross-service contract changes are additive and have contract tests for **both** implementations.
- [ ] Telemetry is considered: no secrets/PII in logs/spans, metric attributes are closed sets, new alerts have a runbook section.
- [ ] **Documentation is updated:** the relevant learning chapter / codebase map / glossary / cheat-sheet / troubleshooting entry — with commands you actually ran.
- [ ] If it touches the generator, templates, compose or observability: `make scaffold-check` (and, with Docker, `make stack-check`) passed.

## 6. Rules you will meet (and where to read why)

| Rule family | Gist | Why |
|---|---|---|
| **B** boundaries | import another service only via its `*_contracts` | [A1·03](docs/learning/phase-a1/03-boundaries-contracts-and-layers.md) |
| **L** layering | `api → application → domain`; no framework imports in the core | [A1·03](docs/learning/phase-a1/03-boundaries-contracts-and-layers.md) |
| **D** data | one schema per service; event + data in one transaction (outbox) | [F·03](docs/learning/foundations/03-databases-for-backend-developers.md) |
| **C** communication | DTOs only, batch, ≤ 1 hop, idempotent handlers | [A1·05](docs/learning/phase-a1/05-a-request-end-to-end.md) |
| **O** observability | log once, structured, no secrets; closed-set labels | [A1·06](docs/learning/phase-a1/06-observability-for-beginners.md) |
| **E** environment | env-only config, health-based startup, pinned images | [A2·02](docs/learning/phase-a2/02-compose-the-whole-system.md) |

## 7. Getting unstuck

1. Read the **first** error line and search [troubleshooting](docs/learning/troubleshooting.md).
2. "Where does this code go?" → [cheat-sheet](docs/learning/cheatsheet.md). "What is this folder?" → [codebase map](docs/learning/kt/01-codebase-map.md).
3. Something running but wrong? Use the [debugging playbook](docs/learning/kt/06-debugging-playbook.md).
4. Still stuck? Ask with: what you ran, what you expected, what happened (full error), what you already tried.

## 8. Improving the docs

Found something unclear or wrong? Fix it in the same PR and run `make docs-check`. If you hit an error a newcomer could hit too, add it to
[troubleshooting](docs/learning/troubleshooting.md). Chapter format: [template](docs/learning/templates/chapter-template.md).
