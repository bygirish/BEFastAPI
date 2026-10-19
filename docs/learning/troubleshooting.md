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

## A debugging recipe that always works
1. **Read the first error line**, not the last. Tracebacks and long tool output usually have the real cause at the top.
2. **Reproduce in the smallest scope:** one package (`make test-service …`), one test (`pytest path::name -x`), one tool (`uv run lint-imports`).
3. **Print the raw data once** (spans, metric points, SQL). Green tests don't prove the emitted data is what you think.
4. **Search this page**, then `docs/architecture/STANDARDS.md` (a rule ID usually explains *why* a check exists).
5. **Add a regression test** for anything that surprised you, and add a line here.
