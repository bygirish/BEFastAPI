# Developer entrypoints. Phase A2 adds compose targets (up/down/logs/obs-smoke/drill).
.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help install sync lint format typecheck arch test test-service new-service scaffold-check \
        obs-sync compose-config up down reset logs ps obs-smoke stack-check docs-check

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Install every workspace package + dev tools
	$(UV) sync --all-packages

sync: ## Regenerate workspace registrations and .importlinter
	$(UV) run python tools/sync_workspace.py

lint: ## ruff + generated-files + architecture contracts + docs health
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run python tools/sync_workspace.py --check
	$(UV) run lint-imports
	$(UV) run python tools/check_docs.py

format: ## Auto-format and fix
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck: ## mypy --strict on every workspace package
	$(UV) run mypy $$($(UV) run python tools/list_packages.py --import-packages | sed 's/\([^ ]*\)/-p \1/g')
	$(UV) run mypy tools/*.py

arch: ## Architecture rules only
	$(UV) run lint-imports

test: ## All tests
	$(UV) run pytest -q

test-service: ## Run one package in isolation: make test-service s=users-service p=services/users/service
	$(UV) run --isolated --package $(s) pytest $(p) -q

new-service: ## Scaffold: make new-service name=files
	$(UV) run python tools/new_service.py $(name)

scaffold-check: ## Generate a throwaway service, run every gate on it, remove it (template-rot guard)
	./tools/scaffold_check.sh

# ----------------------------------------------------------------------------- local stack (Phase A2)
obs-sync: ## Assemble per-service SLO rules + dashboards into deploy/observability/generated
	$(UV) run python tools/sync_observability.py

compose-config: ## Validate docker-compose.yml (no daemon needed)
	docker compose config --quiet && echo "compose config OK"

up: obs-sync ## Build and start everything (profiles come from .env: cp .env.example .env)
	docker compose up -d --build --wait
	@echo "App:     http://localhost:$${APP_PORT:-8000}/docs"
	@echo "Grafana: http://localhost:$${GRAFANA_PORT:-3000}  (admin / admin)"

down: ## Stop containers (keeps data)
	docker compose down --remove-orphans

reset: ## Stop containers AND delete all data volumes
	docker compose down -v --remove-orphans

logs: ## Tail logs: make logs s=app
	docker compose logs -f --tail=100 $(s)

ps: ## Show container status
	docker compose ps

obs-smoke: ## Prove logs/traces/metrics are correlated: make obs-smoke s=<service>
	$(UV) run python tools/obs_smoke.py --service $(s)

stack-check: ## Boot the full stack with a throw-away service, verify, tear down (needs Docker)
	./tools/stack_check.sh

docs-check: ## Docs health: links, anchors, codebase map paths, orphan pages, chapter sections (add EXTERNAL=1 to check URLs)
	$(UV) run python tools/check_docs.py $(if $(EXTERNAL),--external,)
