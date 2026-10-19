# 07 · Adding a Service — Hands-On

**Goal:** generate a service, read what you got, then add a real feature the "contract-first" way — and finish by breaking a rule on purpose.
**Prerequisites:** chapters 01–05, a working `uv sync --all-packages`. **Time:** 1.5–2 hours.

Every command and output in this chapter was run for real. We build a tiny service called **`notes`** with one feature, `shout`, that
upper-cases text and rejects blank text. It's deliberately trivial so you can focus on the *shape* of the work.

---

## 7.1 Generate it

▶ **Try it**
```bash
make new-service name=notes        # same as: uv run python tools/new_service.py notes
uv sync --all-packages
uv run pytest services/notes/service -q
```
```
Created 55 files for service 'notes'
Updated: pyproject.toml, apps/monolith/pyproject.toml, .importlinter
...
.....                                                                    [100%]
5 passed in 1.06s
```
Three files outside `services/notes` were updated for you — all **generated**: the workspace member list, the monolith's dependency list, and `.importlinter`.
It also created `apps/notes_api/` (a standalone entrypoint that runs just this service).

## 7.2 Read what you got

```
services/notes/
├── contracts/…/notes_contracts/     PUBLIC  api.py · dto.py · events.py · errors.py · http_client.py
├── service/
│   ├── migrations/                  own Alembic environment, schema "notes", creates the outbox table
│   ├── tests/                       test_module.py · test_contract.py · conftest.py
│   └── src/notes_service/
│       ├── module.py                the single door the monolith calls
│       ├── settings.py              NOTES_* environment variables
│       ├── contracts_impl.py        in-process implementation of notes_contracts.api
│       ├── api/                     v1 (public) and internal routers + deps.py
│       ├── application/             ports.py · services/ping.py · telemetry.py · handlers/ · jobs/
│       ├── domain/                  errors.py (pure)
│       └── infrastructure/          db/ (models, engine, unit of work) · clients/ · providers/
├── observability/                   slo.yaml · alerts · dashboards/ · runbook.md · README.md (travel with the service)
├── Dockerfile                       for the day this service is extracted
└── README.md                        owner · what it owns · how to run it
```

> 💡 **Learning Thought — everything extraction needs is already inside `services/notes/`.** The code, its public contract, migrations, tests,
> dashboards and Dockerfile. That's why "copy this folder to a new repo" is a realistic plan.

Spend 10 minutes reading, in this order: `contracts/…/api.py` → `module.py` → `application/services/ping.py` → `api/v1/router.py` → `tests/test_contract.py`.
The contract tests run the **same assertions against the in-process implementation and the HTTP client** (parametrised fixture `api`) — that is what proves
extraction won't change behaviour.

## 7.3 Add a feature, contract-first

Order matters. We go **inside-out**: pure rule → contract → use case → wiring → HTTP → tests.

### Step 1 · The business rule + error (domain, pure Python)
```python
# services/notes/service/src/notes_service/domain/errors.py  (added)
class BlankTextError(InvalidInputError):
    default_code = "NOTES_BLANK_TEXT"
    default_message = "Text must not be blank."
```
```python
# services/notes/service/src/notes_service/domain/text.py  (new)
from notes_service.domain.errors import BlankTextError

def shout(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise BlankTextError()
    return cleaned.upper() + "!"
```
Note: no FastAPI, no database. Raising `InvalidInputError` (a *category*) means the platform will turn it into HTTP 422 for us.

### Step 2 · The contract (what other services may call)
```python
# contracts/…/dto.py (added)
class ShoutResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str

# contracts/…/errors.py (added)
class NotesBlankText(InvalidInputError):
    default_code = "NOTES_BLANK_TEXT"
    default_message = "Text must not be blank."

# contracts/…/api.py (added method)
async def shout(self, text: str) -> ShoutResult:
    """Upper-cases text. Raises NotesBlankText for blank input."""
```
…plus the same method on `NotesHttpClient` (calls `GET /internal/v1/notes/shout`, maps `422 NOTES_BLANK_TEXT` back to `NotesBlankText`).

> ⚠️ **Trap — two error classes for "the same" error.** `BlankTextError` (domain, private) and `NotesBlankText` (contract, public) look redundant. They are not:
> other services must never import the domain, so the contract has its own error. The in-process implementation **translates** one into the other, so a
> caller sees the *same* exception whether the service is in-process or remote (rule C-4).

### Step 3 · The use case (application)
```python
# application/services/shout.py (new)
class Shout:
    @traced_use_case
    async def __call__(self, text: str) -> str:
        return shout(text)
```

### Step 4 · Wire it (in-process contract implementation + module)
```python
# contracts_impl.py
class NotesApiImpl:
    def __init__(self, ping: Ping, shout: Shout) -> None: ...

    @traced_contract_call(_CONTRACT)
    async def shout(self, text: str) -> ShoutResult:
        try:
            return ShoutResult(text=await self._shout(text))
        except BlankTextError as exc:
            raise NotesBlankText() from exc          # domain error -> contract error

# module.py  → provide()
shout = Shout()
container.bind(Shout, shout)
container.bind(NotesApi, NotesApiImpl(ping, shout))
```

### Step 5 · Routes (thin!)
```python
# api/v1/router.py (public)
@router.get("/shout", response_model=ShoutResponse)
async def shout(text: str, use_case: ShoutUseCase) -> ShoutResponse:
    return ShoutResponse(text=await use_case(text))
```
The internal router adds the mirror `GET /internal/v1/notes/shout` returning the contract DTO. `deps.py` gains `get_shout`.

### Step 6 · Tests
```python
# tests/test_contract.py — runs for BOTH implementations
async def test_shout_contract(api: NotesApi) -> None:
    assert (await api.shout("  hello ")).text == "HELLO!"

async def test_blank_text_raises_the_same_contract_error_everywhere(api: NotesApi) -> None:
    with pytest.raises(NotesBlankText) as info:
        await api.shout("   ")
    assert info.value.code == "NOTES_BLANK_TEXT"
```
```python
# tests/test_module.py — the public HTTP behaviour and the uniform error body
bad = await client.get("/api/v1/notes/shout", params={"text": "   "})
assert bad.status_code == 422 and bad.json()["error"]["code"] == "NOTES_BLANK_TEXT"
```

### Step 7 · Run every gate
```bash
uv run ruff check services/notes && uv run ruff format --check services/notes
uv run mypy -p notes_service -p notes_contracts -p notes_api
uv run lint-imports
uv run --isolated --package notes-service pytest services/notes/service -q
```
```
ok
Success: no issues found in 37 source files
Contracts: 5 kept, 0 broken.
..........                                                               [100%]
10 passed in 2.98s
```

## 7.4 Run it for real
```bash
export OTEL_SDK_DISABLED=true NOTES_DATABASE_URL="sqlite+aiosqlite:///./notes.db"
# (create tables once on SQLite; with Postgres you'd run Alembic instead — Phase A2)
uv run uvicorn --factory monolith_app.main:create_app --port 8813
curl "localhost:8813/api/v1/notes/shout?text=hello"
curl -i "localhost:8813/api/v1/notes/shout?text=%20%20"
```
```
{"text":"HELLO!"}
HTTP/1.1 422 Unprocessable Entity
{"error":{"code":"NOTES_BLANK_TEXT","message":"Text must not be blank.","details":{},"request_id":"01a152a9-72ba-70bb-b400-36759fd76fe3"}}
```
The monolith found your service on its own through the entry point; you never edited `apps/monolith`.

## 🧪 Labs

### Lab 7.1 — break the domain boundary
Add `import fastapi` to `domain/text.py` and run `uv run lint-imports`. Which contract fails? Fix it by deleting the line.
<details><summary>Solution</summary>

`L-2/L-3: notes_service domain and application never directly import frameworks or vendors → BROKEN`.
</details>

### Lab 7.2 — break the service boundary
Create a *second* service (`make new-service name=other`) and, in `other`'s `application/`, add `from notes_service.domain.text import shout`. What fails and what is the right fix?
<details><summary>Solution</summary>

`B-1: services never import each other's implementation → BROKEN`. Right fix: add `shout` to `notes_contracts`'s API (done in Step 2), define a **port**
in `other` (e.g. `Shouter`), write an adapter in `other/infrastructure/clients/` that calls `NotesApi`, and let `apps/monolith/wiring.py` bind it. Remove the second service with
`rm -rf services/other apps/other_api && uv run python tools/sync_workspace.py`.
</details>

### Lab 7.3 — a business metric
Add `notes.shouted` (counter, attribute `outcome ∈ {ok, blank}`) in `application/telemetry.py`, increment it in `Shout`, and assert it in a test using
`platform_observability.testing`. Why is `outcome` allowed but `text` not?
<details><summary>Solution</summary>

`text` is unbounded free text (high cardinality *and* possibly personal data). Test pattern: see `libs/platform_observability/tests/test_telemetry_contract.py`.
</details>

### Lab 7.4 — an event with a subscriber
Define `notes.text_shouted.v1`, add it to the outbox in a (new) use case, subscribe a handler wrapped in `idempotent(...)` in `register_event_handlers`, and prove it runs once even if delivered twice.
<details><summary>Hint</summary>

Copy the `Ping` use case for the outbox write; see `libs/platform_events/tests/test_events.py::test_idempotent_handler_runs_once` for the idempotency test.
</details>

## 7.5 Clean up
```bash
rm -rf services/notes apps/notes_api
uv run python tools/sync_workspace.py && uv sync --all-packages
```
Or let `make scaffold-check` do generate → verify → remove in one go.

## 🎯 Interview Questions
1. **Why build the contract before the implementation?** *The contract is the promise other teams code against; designing it first keeps internals from leaking
   into it and forces you to think about batching, errors and versioning.*
2. **Why do the in-process and HTTP implementations share one test suite?** *If both pass identical assertions, swapping one for the other (extraction)
   cannot change behaviour — the test is the proof.*
3. **A use case needs data from another service. What do you add?** *A port in the consumer's `application/ports.py`, an adapter in `infrastructure/clients/`
   that uses the provider's contract, and a binding in `apps/*/wiring`.*
4. **Why generate services instead of copy-pasting an existing one?** *A generator produces a known-good, rule-compliant skeleton (and a CI "scaffold check" keeps it that way); copies drift and inherit old mistakes.*

## ✅ Self-check
- [ ] I can generate a service and name what each top-level folder is for.
- [ ] I can add a feature in the order domain → contract → use case → wiring → route → tests.
- [ ] I can explain why the domain error and the contract error are different classes.
- [ ] I can trigger and read both an L- and a B- architecture failure.

## 📚 Further reading
- FastAPI — *Dependencies*: <https://fastapi.tiangolo.com/tutorial/dependencies/>
- FastAPI — *Handling errors*: <https://fastapi.tiangolo.com/tutorial/handling-errors/>
- Alembic tutorial: <https://alembic.sqlalchemy.org/en/latest/tutorial.html>

**Next:** [08 · Quality gates & CI →](08-quality-gates-and-ci.md)
