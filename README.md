# BEFastAPI

An extraction-ready **modular monolith** built with FastAPI: Auth, Users, Files, Notifications … live in one deployable app today, but each
service is isolated so strictly (own contract, own data, own config, own observability) that it can be lifted into its own repo in about a day or two.

## Quick start

```bash
make install                 # uv sync --all-packages  (needs Python 3.12 and uv)
make lint typecheck test     # ruff + architecture rules + mypy --strict + pytest
make new-service name=notes  # scaffold a service (contracts, implementation, migrations, observability, tests)

cp .env.example .env         # then run EVERYTHING in containers (needs Docker):
make up                      # postgres, redis, migrations, app, collector, tempo, loki, prometheus, grafana …
#   Grafana http://localhost:3000 (admin/admin) · app http://localhost:8000/docs
#   (port 8000 busy?  APP_PORT=18000 make up)
make stack-check             # boot + verify + tear down, with a throw-away service
make demo                    # live demo: everything + a throw-away service + background traffic (make demo-down to stop)
```

## Documentation map

| If you want to… | Read |
|---|---|
| **Learn the project from scratch** (beginner friendly, with labs) | [`docs/learning/00-INDEX.md`](docs/learning/00-INDEX.md) |
| **Join the project** (day-by-day plan, codebase map) | [Onboarding plan](docs/learning/kt/02-reading-guide-and-onboarding-plan.md) · [CONTRIBUTING](CONTRIBUTING.md) |
| **Test yourself** (60 questions, capstone project, skills matrix) | [Assessments](docs/learning/assessments/01-question-bank.md) |
| Look up a rule, a command or an error | [Cheat-sheet](docs/learning/cheatsheet.md) · [Glossary](docs/learning/glossary.md) · [Troubleshooting](docs/learning/troubleshooting.md) |
| Understand the architecture decisions | [`docs/architecture/`](docs/architecture/README.md) |
| Know what the code must / must not do | [`docs/architecture/STANDARDS.md`](docs/architecture/STANDARDS.md) |
| See the Auth + RBAC design | [`services/auth/docs/PLAN.md`](services/auth/docs/PLAN.md) |
| Move a service into its own repo | [`docs/architecture/EXTRACTION_PLAYBOOK.md`](docs/architecture/EXTRACTION_PLAYBOOK.md) |

## Repository layout

```
apps/       composition roots (the only place that wires services together)
libs/       shared, business-agnostic platform libraries (core, events, http, security, observability)
services/   one folder per service: contracts/ (public) · service/ (private) · observability/
tools/      service generator, workspace sync, scaffold check
docs/       architecture/ (specifications) · learning/ (beginner guide)
```

## Status

Phases A1 (foundation) and A2 (Docker Compose + observability stack) are implemented and verified. Next: Notifications → Auth → Users → Files.
See the [roadmap](docs/architecture/README.md#roadmap-no-code-yet).
