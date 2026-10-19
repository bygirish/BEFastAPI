#!/usr/bin/env bash
# Guards against template rot: scaffold a throwaway service, run every gate on it, then remove it.
# Used by CI (job `scaffold`) and locally via `make scaffold-check`.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:-scaffoldcheck}"

cleanup() {
  rm -rf "services/${NAME}" "apps/${NAME}_api"
  uv run python tools/sync_workspace.py >/dev/null 2>&1 || .venv/bin/python tools/sync_workspace.py >/dev/null
  uv sync --all-packages --quiet || true
}
trap cleanup EXIT

uv run python tools/new_service.py "${NAME}"
uv sync --all-packages --quiet
uv run ruff check "services/${NAME}" "apps/${NAME}_api"
uv run ruff format --check "services/${NAME}" "apps/${NAME}_api"
uv run mypy -p "${NAME}_service" -p "${NAME}_contracts" -p "${NAME}_api"
uv run lint-imports
uv run --isolated --package "${NAME}-service" pytest "services/${NAME}/service" -q -p no:cacheprovider
echo "scaffold-check OK"
