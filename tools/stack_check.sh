#!/usr/bin/env bash
# Boots the WHOLE stack with a throw-away service, proves the signals are correlated, then removes everything.
# Needs a running Docker daemon. Used by `make stack-check` and the nightly workflow.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:-stackcheck}"
export COMPOSE_PROFILES="obs"
# Override when 8000 is taken on your machine:  APP_PORT=18000 make stack-check
export APP_PORT="${APP_PORT:-8000}"

cleanup() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "--- FAILED (exit $rc): container status and logs"
    docker compose ps -a || true
    docker compose logs --no-color --tail=60 app "migrate-${NAME}" db-provision || true
  fi
  echo "--- cleanup"
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "services/${NAME}" "apps/${NAME}_api"
  uv run python tools/sync_workspace.py >/dev/null 2>&1 || .venv/bin/python tools/sync_workspace.py >/dev/null
  uv run python tools/sync_observability.py >/dev/null 2>&1 || true   # drop the throw-away service's generated rules
  uv lock --quiet || true
  uv sync --all-packages --quiet || true
}
trap cleanup EXIT

uv run python tools/new_service.py "${NAME}" >/dev/null
uv sync --all-packages --quiet        # refreshes uv.lock so the image build (--frozen) sees the new service
uv run python tools/sync_observability.py
docker compose config --quiet
docker compose up -d --build --wait
# A stack that was already running keeps its OLD rule files (Prometheus doesn't watch them): SIGHUP makes it re-read them.
docker compose kill -s HUP prometheus >/dev/null 2>&1 || true
sleep 3
docker compose ps
uv run python tools/obs_smoke.py --service "${NAME}" --app "http://localhost:${APP_PORT}"
echo "stack-check OK"
