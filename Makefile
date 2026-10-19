# Developer entrypoints. Phase A2 adds compose targets (up/down/logs/obs-smoke/drill).
.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help install sync lint format typecheck arch test test-service new-service scaffold-check

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Install every workspace package + dev tools
	$(UV) sync --all-packages

sync: ## Regenerate workspace registrations and .importlinter
	$(UV) run python tools/sync_workspace.py

lint: ## ruff + generated-files check + import-linter (architecture)
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run python tools/sync_workspace.py --check
	$(UV) run lint-imports

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
