#!/usr/bin/env bash
# Live demo of the whole platform.
#
#   tools/demo.sh up       boot everything with a throw-away "demo" service + background traffic
#   tools/demo.sh status   what is running
#   tools/demo.sh down     stop everything and remove the demo service again
#
# Needs: Docker running, uv. Port 18000 is used by default (APP_PORT=… to change).
set -euo pipefail
cd "$(dirname "$0")/.."

ACTION="${1:-up}"
NAME=demo
STATE=.demo
export APP_PORT="${APP_PORT:-18000}"
export COMPOSE_PROFILES="${COMPOSE_PROFILES:-obs,tools}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
mkdir -p "$STATE"

# A root-owned ~/.docker/buildx (left by an old `sudo docker`) makes `docker build` fail; work around it privately.
if [ -e "$HOME/.docker/buildx/current" ] && [ ! -r "$HOME/.docker/buildx/current" ]; then
  mkdir -p "$STATE/docker-config"
  cp "$HOME/.docker/config.json" "$STATE/docker-config/config.json" 2>/dev/null || echo '{}' > "$STATE/docker-config/config.json"
  ln -sfn "$HOME/.docker/cli-plugins" "$STATE/docker-config/cli-plugins"
  export DOCKER_CONFIG="$PWD/$STATE/docker-config"
  echo "note: ~/.docker/buildx is not readable; using a private Docker config (fix: sudo chown -R \"\$USER\" ~/.docker)"
fi

stop_traffic() {
  if [ -f "$STATE/traffic.pid" ]; then
    kill "$(cat "$STATE/traffic.pid")" 2>/dev/null || true
    rm -f "$STATE/traffic.pid"
  fi
}

patch_demo_service() {
  # Throw-away demo endpoints (a slow call and a "bug") so the dashboards have something interesting to show.
  python3 - <<PY
import pathlib
p = pathlib.Path("services/$NAME/service/src/${NAME}_service/api/v1/router.py")
s = p.read_text()
if "def slow" not in s:
    s = s.replace("from fastapi import APIRouter\n", "import asyncio\n\nfrom fastapi import APIRouter\n\nfrom platform_observability import start_span\n", 1)
    s += '''

@router.get("/slow")
async def slow(ms: int = 400) -> dict[str, int]:
    with start_span("$NAME.slow_work", attributes={"work.ms": ms}):
        await asyncio.sleep(ms / 1000)
    return {"slept_ms": ms}


@router.get("/fail")
async def fail() -> None:
    raise RuntimeError("demo: simulated bug")
'''
    p.write_text(s)
PY
  uv run ruff check --fix -q "services/$NAME" "apps/${NAME}_api" || true
  uv run ruff format -q "services/$NAME" "apps/${NAME}_api" || true
}

case "$ACTION" in
  up)
    docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and retry."; exit 1; }
    if lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN >/dev/null 2>&1 && ! docker compose ps --status running 2>/dev/null | grep -q app; then
      echo "Port $APP_PORT is already in use by another process. Choose another: APP_PORT=18001 tools/demo.sh up"; exit 1
    fi
    [ -f .env ] || { cp .env.example .env; echo "created .env from .env.example"; }
    if [ ! -d "services/$NAME" ]; then
      uv run python tools/new_service.py "$NAME" >/dev/null
      patch_demo_service
    fi
    uv sync --all-packages --quiet
    uv run python tools/sync_observability.py >/dev/null
    docker compose up -d --build --wait
    stop_traffic
    nohup uv run python tools/demo_traffic.py --base "http://localhost:$APP_PORT" --service "$NAME" > "$STATE/traffic.log" 2>&1 &
    echo $! > "$STATE/traffic.pid"
    cat <<TXT

  The platform is up, with background traffic flowing.

    App docs        http://localhost:$APP_PORT/docs
    Grafana         http://localhost:$GRAFANA_PORT      (admin / admin)  -> Dashboards > Platform > "RED overview"
    Prometheus      http://localhost:9090              (alerts: /alerts)
    Alertmanager    http://localhost:9093
    Mailpit / DB    http://localhost:8025  /  http://localhost:8080

  Presenter script:  docs/learning/kt/08-demo-script.md
  Stop and clean up: tools/demo.sh down      (or: make demo-down)
TXT
    ;;
  status)
    docker compose ps -a 2>/dev/null | head -30 || true
    if [ -f "$STATE/traffic.pid" ] && kill -0 "$(cat "$STATE/traffic.pid")" 2>/dev/null; then
      echo "traffic generator: running (pid $(cat "$STATE/traffic.pid")); last line:"; tail -1 "$STATE/traffic.log" 2>/dev/null || true
    else
      echo "traffic generator: not running"
    fi
    ;;
  down)
    stop_traffic
    docker compose down -v --remove-orphans || true
    rm -rf "services/$NAME" "apps/${NAME}_api"
    uv run python tools/sync_workspace.py >/dev/null 2>&1 || .venv/bin/python tools/sync_workspace.py >/dev/null
    uv run python tools/sync_observability.py >/dev/null 2>&1 || true
    uv lock --quiet || true
    uv sync --all-packages --quiet || true
    rm -rf "$STATE"
    echo "demo stopped and the demo service removed."
    ;;
  *)
    echo "usage: tools/demo.sh up|status|down"; exit 2 ;;
esac
