# BEFastAPI

An extraction-ready **modular monolith** built with FastAPI: Auth, Users, Files, Notifications … live in one deployable app today, but each
service is isolated so strictly (own contract, own data, own config, own observability) that it can be lifted into its own repo in about a day or two.

## Quick start

```bash
make install                 # uv sync --all-packages  (needs Python 3.12 and uv)
make lint typecheck test     # ruff + architecture rules + mypy --strict + pytest
make new-service name=notes  # scaffold a service (contracts, implementation, migrations, observability, tests)
uv run uvicorn --factory monolith_app.main:create_app --reload   # run every installed service in one process
```

## Documentation map

| If you want to… | Read |
|---|---|
| **Learn the project from scratch** (beginner friendly, with labs) | [`docs/learning/00-INDEX.md`](docs/learning/00-INDEX.md) |
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

Phase A1 (foundation) is implemented. Next: A2 (Docker Compose + observability stack), then Notifications → Auth → Users → Files.
See the [roadmap](docs/architecture/README.md#roadmap-no-code-yet).
