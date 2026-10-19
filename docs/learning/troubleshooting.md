# Troubleshooting — real errors we hit (and what they meant)

Every entry below happened while building Phase A1. Format: **symptom → cause → fix → lesson**.
Search this page for the first line of your error message.

---

## Environment & tooling

### 1. `uv`: `Failed to initialize cache at ~/.cache/uv … Permission denied`
- **Cause:** the cache directory was owned by `root` (created once with `sudo`).
- **Fix:** `sudo chown -R "$USER" ~/.cache/uv`. Temporary workaround: `export UV_CACHE_DIR=/some/writable/dir`.
- **Lesson:** never run package managers with `sudo`; it leaves root-owned files that break the next normal run.

### 2. `git`: `insufficient permission for adding an object to repository database .git/objects`
- **Cause:** some `.git/objects/xx` folders were root-owned, so git couldn't write new objects that hashed into them. It looks random because only *certain* files fail.
- **Fix:** `sudo chown -R "$USER" .git`; verify with `find .git -user root | wc -l` → `0`.
- **Lesson:** same as above. Also: a partial failure means *nothing* was committed — check `git status` before retrying.

### 3. `uv`: `Workspace member … is missing a pyproject.toml (matches: services/*)`
- **Cause:** the workspace used a glob (`services/*`) and one matched folder (`services/auth`) only had docs.
- **Fix:** list members explicitly. We generate that list (`tools/sync_workspace.py`).
- **Lesson:** globs are convenient until a stray folder appears.

### 4. `uv`: `Project is contained in non-workspace project` / `… references a workspace … but is not a workspace member`
- **Cause:** we nested `contracts/` *inside* the service package folder; uv doesn't allow a member inside another member.
- **Fix:** make them siblings: `services/<n>/service/` and `services/<n>/contracts/`.
- **Lesson:** see chapter 02 §2.4.

### 5. `pydantic_settings … error parsing value for field "enabled_services"`
- **Cause:** for list-typed fields pydantic-settings expects JSON (`["a","b"]`), but we pass `ENABLED_SERVICES=auth,users`.
- **Fix:** annotate with `NoDecode` and split in a validator: `Annotated[list[str], NoDecode]` + `field_validator(mode="before")`.
- **Lesson:** env vars are strings; decide how lists are encoded.

### 6. `pytest: Invalid regex '*_service': nothing to repeat`
- **Cause:** `filterwarnings` takes **regex**, not globs. `*_service` is not a valid regex.
- **Fix:** `.*_service`.

## Architecture checks

### 7. `import-linter: Could not find package 'redis' in your Python path`
- **Cause:** third-party packages named in a contract must be installed so the graph can see them.
- **Fix:** add the package to the dev dependency group (even if no code imports it yet).

### 8. `import-linter: Missing layer in container 'x_service': module x_service.x_service.application does not exist`
- **Cause:** with `containers = x_service`, layer names are relative. We wrote the full path.
- **Fix:** `layers = api | infrastructure / application / domain`.

## Typing

### 9. `mypy: Package 'platform_core' cannot be type checked due to missing py.typed marker`
- **Fix:** add an empty `py.typed` file to the package (PEP 561). The generator does it for new services.

### 10. `mypy: May only specify one of: module/package, files, or command`
- **Fix:** don't mix `-p pkg` and file paths in one call; run mypy twice.

### 11. `Incompatible return value type … Following member(s) of "SqlUnitOfWork" have conflicts: outbox`
- **Cause:** Protocol attribute was mutable → invariant. **Fix:** declare it as a read-only `@property`. Explained in chapter 08 §8.2.

## Telemetry

### 12. Test sees `[]` for spans
- **Cause:** `OTEL_SDK_DISABLED=true` was set in the environment (our scaffold script exported it by mistake).
- **Fix:** unset it when asserting on telemetry. It is for "run without exporting" in production-like runs only.

### 13. Two `http.server.request.duration` series per request
- **Cause:** FastAPI's built-in telemetry *and* our middleware both emit the metric. **Fix:** switch FastAPI's metrics/logs off. Explained in chapter 06 §6.5.

### 14. `BrokenPipeError` + a wall of `--- Logging error ---` when piping a script to `head`
- **Cause:** `head` closed the pipe while the app was still logging to stdout. Harmless, but noisy and it can hide the output you wanted.
- **Fix:** write to a file then read it, or don't truncate with `head`.

## Data & IDs

### 15. UUIDv7 values not in creation order
- **Cause:** random bits where a counter was needed for same-millisecond ordering. **Fix:** monotonic counter (`libs/platform_core/src/platform_core/ids.py`). Chapter 04 §4.1.

---

## Docker, Compose and the live stack (Phase A2)

### 16. `open ~/.docker/buildx/current: permission denied` when building
- **Cause:** root-owned files inside `~/.docker/buildx` (created once by a `sudo docker`). **Fix:** `sudo chown -R "$USER" ~/.docker`. Automation workaround: point `DOCKER_CONFIG` at a private copy of `~/.docker`.

### 17. Container exits at once: `ModuleNotFoundError: No module named 'redis'`
- **Cause:** the production image has no dev dependencies; start-up imported an optional instrumentation unconditionally. **Fix:** only instrument installed libraries; test the "absent" case. (A2·01 §1.3)

### 18. App crashes at start-up inside logging: `AttributeError: 'str' object has no attribute 'copy'`
- **Cause:** our OTLP log handler formatted each record twice; structlog's formatter expects the event dict the second time. **Fix:** render once, pass a clean record; make the handler exception-safe. (A2·04)

### 19. A warning on every log line: `Invalid type … _FixedFindCallerLogger for attribute value`
- **Cause:** structlog's private record attributes were exported as OpenTelemetry attributes. **Fix:** strip them before export.

### 20. Migration job exits 0 but `relation "<svc>.outbox" does not exist`
- **Cause:** a query before `context.begin_transaction()` auto-started a transaction, so Alembic didn't commit; closing the connection rolled back. **Fix:** `connection.commit()` first. (A2·02 §2.5)

### 21. `/readyz` returns 404 from `localhost:8000` although `docker compose ps` says healthy
- **Cause:** another process owns `127.0.0.1:8000`. **Diagnose:** `lsof -nP -iTCP:8000 -sTCP:LISTEN`. **Fix:** `APP_PORT=18000`.

### 22. Docker created a root-owned folder in the repo
- **Cause:** a bind-mounted host path did not exist. **Fix:** keep placeholders in git (`.gitkeep`); `make obs-sync` recreates them.

### 23. Dashboard panel shows *No data*
Work through: (1) is there traffic in the time range? (2) does the metric exist? `curl localhost:9090/api/v1/label/__name__/values` (3) are label names what the query expects (`app_service`, not `app.service`)? (4) did a rate window need more samples? (5) legitimately empty (e.g. no 5xx yet)? We validated every panel query against live Prometheus before shipping.

### 24. Collector panel/alert empty: metric not found
- **Cause:** `otelcol_receiver_accepted_spans` has **no `_total` suffix** in this collector version. **Fix:** query the real names. Always check names with the label-values API.

### 25. Grafana shows "Loading plugin panel…" for a long time
- Panels lazy-load JavaScript; on a 2-CPU Docker VM the first dashboard open takes ~20 s. Wait; later loads are fast.

### 26. pytest: `ERROR … _xunit_setup_module_fixture` at collection
- **Cause:** a module-level name `setup_module` (even an import alias) is treated as an xunit fixture. **Fix:** rename. Related: `from pkg import setup` may return a re-exported *function*, not the submodule — use `importlib.import_module("pkg.setup")`.

### 27. Docker out of memory / slow
- Check Docker Desktop's memory (this stack used ≈ 0.46 GB for 14 containers; 3 GB total was enough). `docker stats --no-stream` shows who is heavy; `docker system df` shows disk.

### 28. A 500 response says `"request_id": null`
- **Cause:** Starlette's own 500 handler runs *outside* all user middleware, after the request id was cleared. **Fix:** `UnhandledErrorMiddleware` inside the observability middleware (found by the Postgres-down drill, [KT·06](kt/06-debugging-playbook.md)). Regression test in `apps/monolith/tests`.

### 29. Log flood: the same error 40 times a minute while the database is down
- **Cause:** the outbox relay retried every 0.5 s and logged a traceback each time. **Fix:** exponential backoff capped at 30 s, one traceback then short reminders, `outbox_relay_recovered` on healing.

### 30. A dead-lettered outbox row says only "1 handler(s) failed"
- **Cause:** the underlying exception wasn't in `last_error`. **Fix:** `EventDeliveryError` now includes `handler: ExcType: message`.

### 31. Generated contract test breaks after I add a constructor argument
- **Cause:** the test hand-built the in-process implementation. **Fix:** resolve it from the container (`app.state.container.resolve(<Name>Api)`) — the scaffold does this now.

### 32. `make docs-check` fails: "codebase map lists a path that does not exist" / "orphan page" / "anchor not found"
- Renamed/deleted a file? Update `docs/learning/kt/01-codebase-map.md`. New page? Link it from `docs/learning/00-INDEX.md`. Anchor: GitHub slugs drop punctuation and emoji and turn spaces into hyphens (`## 2.1 The problem` → `#21-the-problem`).

### 33. pytest: `ModuleNotFoundError: No module named 'conftest'`
- **Cause:** the repo runs pytest in `importlib` mode; `conftest.py` provides fixtures but is not an importable module. **Fix:** put shared helper code in the package (e.g. `notifications_service/testing.py`) and import that. 🔗 [B·03 P6](phase-b/03-what-the-live-run-taught-us.md)

### 34. A Prometheus query / alert returns nothing (empty result, no error)
- **Cause:** a misspelt or un-suffixed name — PromQL treats an unknown metric as "no series". Counters exported via OpenTelemetry end in `_total`, histograms in `_seconds_bucket/_count/_sum`. **Fix:** `curl -s localhost:9090/api/v1/label/__name__/values` and copy the real name; `counter_ratio` SLOs are now validated to end in `_total`. 🔗 [B·03 P3](phase-b/03-what-the-live-run-taught-us.md)

### 35. The SLO ratio is `0` or `NaN` although errors just happened
- **Cause:** a counter series that first appears already at N has no earlier sample, so `rate()`/`increase()` see no change; or there was simply no traffic in the window (`0/0 = NaN`). **Fix:** publish all closed-set series at 0 on start-up (`prime_metrics`); widen the window or send traffic. 🔗 [B·03 P4](phase-b/03-what-the-live-run-taught-us.md)

### 36. `refusing to start in production: dev-only providers ['console'] are configured; …`
- **Cause:** `ENV=production` with a development setting (console/memory/static provider, `NOTIFICATIONS_DEV_ENDPOINTS=true`, or the default `NOTIFICATIONS_DIGEST_PEPPER`). It is deliberate (rule X-11). **Fix:** configure a real provider chain and a real pepper; never "work around" it. 🔗 [B·02 §2.12](phase-b/02-hands-on-live-stack.md)

### 37. My email went to the app log instead of Mailpit
- **Cause:** the chain is `smtp,console`; if Mailpit is stopped or the `tools` profile is off, `smtp` is `unavailable` and the gateway **fails over** to `console` (a feature, shown by `attempts: 2` and a `provider_failover` log line). **Fix:** `docker compose up -d mailpit` (and `COMPOSE_PROFILES=obs,tools`). 🔗 [B·02 §2.5](phase-b/02-hands-on-live-stack.md)

### 38. Dev endpoint answers `429 NOTIFICATIONS_RATE_LIMITED`
- **Cause:** more than `NOTIFICATIONS_RATE_LIMIT_PER_HOUR` deliveries to the same (normalised) recipient in the last hour. **Fix:** use another recipient, or `NOTIFICATIONS_RATE_LIMIT_PER_HOUR=500 docker compose up -d --wait app`. `Retry-After` says when the oldest delivery leaves the window.

### 39. `422 NOTIFICATIONS_TEMPLATE_VARIABLES` with `missing`/`unexpected` lists
- **Cause:** templates need *exactly* their variables (`otp`: `code`, `ttl_minutes`; `welcome`: `name`; `password_changed`: none). The `details` field names what is missing or extra.

### 40. A new service's SLO alerts are missing in Prometheus (`group <svc>-slo not loaded`)
- **Cause:** `make obs-sync` wrote the rule files, but a Prometheus that was **already running** doesn't watch them (it reads rules at start and on reload). `make stack-check` hit this on a stack that had been up for a while. **Fix:** `docker compose kill -s HUP prometheus` (SIGHUP = reload config and rules); `make up`, `make stack-check` and `make demo` now do this for you.

---

## A debugging recipe that always works
1. **Read the first error line**, not the last. Tracebacks and long tool output usually have the real cause at the top.
2. **Reproduce in the smallest scope:** one package (`make test-service …`), one test (`pytest path::name -x`), one tool (`uv run lint-imports`).
3. **Print the raw data once** (spans, metric points, SQL). Green tests don't prove the emitted data is what you think.
4. **Search this page**, then `docs/architecture/STANDARDS.md` (a rule ID usually explains *why* a check exists).
5. **Add a regression test** for anything that surprised you, and add a line here.
