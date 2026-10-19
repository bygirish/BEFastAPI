# KT · 08 — Demo Script (15–20 minutes)

**Goal:** show the whole platform working — and *why it's built this way* — to a teammate, a manager or a new joiner, using one command and a live system.
**Prerequisites:** Docker Desktop running (≥ 3 GB for Docker), `uv`, free ports 3000, 9090, 9093, 18000. **Everything below was rehearsed on the real stack.**

---

## 0. Before the audience arrives (≈ 3 min, 5+ min the first time because images download)

```bash
make demo            # = tools/demo.sh up : boots the stack with a throw-away "demo" service + background traffic
```
It prints the URLs. Open these tabs and log into Grafana (`admin` / `admin`):

| Tab | URL |
|---|---|
| ① Grafana → Dashboards → Platform → **RED overview** | `http://localhost:3000` |
| ② Prometheus alerts | `http://localhost:9090/alerts` |
| ③ App docs (OpenAPI) | `http://localhost:18000/docs` |
| ④ Terminal in the repo | — |

Wait ~3 minutes after boot so the graphs fill and an alert fires (the traffic generator deliberately sends ~4 % bugs and ~10 % slow requests).
Check readiness: `make demo-status` shows the traffic generator and containers.

> **Port 8000 busy?** The demo uses 18000 by default. **Docker permission error on build?** The script detects a root-owned `~/.docker/buildx` and works around it (it tells you).

## 1. The idea in two minutes (diagrams, no code)
*Show [KT·04](04-architecture-diagrams.md) diagrams 2 and 7.*
- "One app today, built from services that are **separated like they're already remote**: each owns its data (one DB schema), exposes a tiny **contract**, and talks to others only through contracts and events."
- "Extraction later = change one wiring line and move one schema. That promise is **enforced by tools**, not by good intentions."
- "And we can *see inside* it: logs, metrics and traces linked together."

## 2. The rules are enforced (≈ 2 min, live)
```bash
uv run python tools/new_service.py shop --dry-run | head -8           # a service is generated, not hand-copied (nothing written)
F=services/demo/service/src/demo_service/domain/errors.py
cp "$F" /tmp/errors.py.bak                        # keep a copy so the demo can be undone exactly
printf '\nimport fastapi\n' >> "$F"              # a "harmless" import of a web framework inside the domain layer
uv run lint-imports | tail -8                     # BROKEN: the domain layer must not import a web framework
cp /tmp/errors.py.bak "$F"                        # undo
uv run lint-imports | grep "Contracts:"           # kept again
```
Say: "The build fails the moment someone breaks a boundary — that's what keeps extraction cheap." (The demo service is throw-away and untracked, so nothing else needs undoing.)

## 3. Talk to the live system (≈ 2 min)
```bash
curl -i -H "X-Request-ID: demo-live-1" localhost:18000/api/v1/demo/ping
curl -s localhost:18000/readyz | python3 -m json.tool
```
Point out: the `x-request-id` echoed back; `/readyz` aggregating each service's own health check (liveness vs readiness).

## 4. The RED dashboard (≈ 3 min) — tab ①
- **Service** drop-down = *logical* service (`app.service`), not the process — it will keep working after extraction.
- **Request rate** (~3 req/s), **Error ratio** (5xx only; 4xx are caller mistakes), **Latency p95 by route** (note `/slow` vs `/ping`), **Status codes**, **Spans/s**, **Recent logs**.
- "Why 5xx only? **4xx means you, 5xx means us** — only ours burn the error budget."

## 5. From a number to the story (≈ 3 min) — the 3-click promise
1. On *Latency p95 by route*, click a **diamond** (an *exemplar*: a real request in that latency bucket) → *Query with Tempo*.
2. In the trace, find the long span (`demo.slow_work`) — "this is where the time went".
3. Click **Logs for this span** → the JSON log lines of exactly that request (`trace_id`, `request_id`, `app.service`).

> Say it plainly: "No magic — the same `trace_id` string is written into the log, the span and the metric, and Grafana is configured **as code** to turn it into links."

## 6. A real failure (≈ 3 min)
```bash
curl -i -H "X-Request-ID: demo-boom-1" localhost:18000/api/v1/demo/fail
```
- The user sees a **500 with a `request_id`** (not a stack trace). "That id is what a customer quotes to support."
- Grafana → Explore → **Loki**: `{service_name=~".+"} |= "demo-boom-1"` → the `unhandled_exception` line with the stack trace → **Open trace** → the root span has a **red error status**.
- "We rehearsed this failure and found two bugs in our own error handling — now fixed with tests" ([A2·04](../phase-a2/04-what-the-live-run-taught-us.md), [KT·06](06-debugging-playbook.md)).

## 7. Alerts that mean something (≈ 2 min) — tab ②
- `DemoAvailabilityBudgetBurn` **firing** (page), the slower-burn variants **pending**.
- "These rules are **generated** from a 10-line `slo.yaml` in the service folder: multi-window burn-rate alerts, each linked to a runbook section — the generator refuses to build without one."
- Optional: `http://localhost:9093` (Alertmanager) shows the same alert routed.

## 8. It survives failures (optional, ≈ 2 min)
```bash
docker compose stop postgres ; curl -s -i localhost:18000/readyz | head -1 ; curl -s localhost:18000/livez
docker compose start postgres
```
`readyz` → 503 (not ready), `livez` → ok (process fine, nothing to restart); after `start`, `readyz` recovers in seconds with **zero container restarts**.
Also: `docker compose stop otel-collector` → requests still succeed — **telemetry is best-effort and never takes the app down**.

## 9. Close (≈ 1 min)
- "Today: foundation, local stack, observability — verified end to end, with a beginner learning guide and an automated docs check."
- "Next: Notifications → Auth + RBAC → Users → Files, then a **split rehearsal**" ([KT·07](07-roadmap-and-prereading.md)).
- Point to [`docs/learning/00-INDEX.md`](../00-INDEX.md) for self-study and the [capstone](../assessments/02-capstone-project.md).

## 10. Clean up
```bash
make demo-down       # stops traffic + containers, deletes volumes, removes the throw-away service
```

## If something goes wrong mid-demo
| Symptom | Quick fix |
|---|---|
| Dashboard panels spin or say *No data* | wait ~20 s (first load is slow on a small Docker VM); send traffic: `make demo-status` should show the generator running |
| No alert firing yet | alerts need ~2–3 min of traffic; show the generated rules file `deploy/observability/generated/rules/demo.slo.rules.yml` meanwhile |
| Grafana asks to log in | `admin` / `admin` |
| `curl` to 18000 fails | `make demo-status`; `docker compose logs app` |
| Everything is wedged | `make demo-down && make demo` |

## 🎯 Interview Questions (what the audience may ask — and answers)
1. **"Isn't this over-engineered for one app?"** *The discipline is cheap now (generators + CI checks) and the payoff is extraction in days instead of months; and we didn't pay for microservices' operational costs.*
2. **"How do you know the services are really independent?"** *Architecture rules fail the build; each package is tested in isolation; and the stack-check/extraction drill proves a service boots and migrates alone.*
3. **"What happens if observability is down?"** *The app keeps serving (we proved it); logs still go to stdout; we alert on the collector dropping data.*
4. **"Can we use another vendor than Grafana?"** *Yes: the app speaks only OpenTelemetry to a collector; swapping backends is collector configuration.*

## ✅ Self-check (for the presenter)
- [ ] I ran `make demo` beforehand and saw an alert firing.
- [ ] I can do steps 5 and 6 without notes (exemplar → trace → logs; request id → logs).
- [ ] I know how to clean up (`make demo-down`).

**Back to the [index](../00-INDEX.md).**
