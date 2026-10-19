# F · 01 — The Python You Need for This Codebase

**Goal:** understand the seven Python features this project leans on — type hints, `Protocol`, `dataclass` vs Pydantic, `async`/`await`, context managers, decorators and generics — well enough to read any file here.
**Prerequisites:** you can write basic Python (functions, classes, lists, dicts). **Time:** 1–1.5 hours.
Every output below was produced by running the snippet (Python 3.12).

> **How to use this chapter:** copy each snippet into a scratch file, run it, then change something and predict the result before you run it again.
> That prediction habit is the fastest way to learn.

---

## 1.1 Type hints — documentation that a tool can check

```python
def double(x: int) -> int:
    return x * 2

print(double("ab"))
```
```
abab
```
**Python itself ignores type hints.** It happily multiplied a string. A separate tool, **mypy**, reads the hints and complains *before* you run the program. We run `mypy --strict` in CI
([A1 · 08](../phase-a1/08-quality-gates-and-ci.md)), so a wrong type is a build failure, not a production bug.

| You write | Means |
|---|---|
| `x: int` | an integer |
| `name: str \| None` | a string **or** `None` ("optional") |
| `items: list[str]` | a list of strings |
| `data: dict[str, int]` | keys are strings, values are ints |
| `-> None` | the function returns nothing useful |
| `Callable[[int], str]` | a function taking an int and returning a str |

> 💡 **Learning Thought — hints are a conversation with your future self.** `def charge(user_id: UUID, amount_cents: int) -> Receipt` tells the next developer (and mypy) exactly what goes in and out without reading the body.

## 1.2 `dataclass` vs Pydantic — two ways to hold data

```python
from dataclasses import dataclass, FrozenInstanceError
from pydantic import BaseModel, ValidationError

@dataclass(frozen=True)
class Point:
    x: int
    y: int

p = Point(1, 2)
p.x = 5                       # FrozenInstanceError: it is immutable
Point("a", "b")               # works!  Point(x='a', y='b')  -- a dataclass does NOT validate

class User(BaseModel):
    name: str
    age: int

User(name="Ann", age="not-a-number")     # ValidationError
User(name="Ann", age="42").age           # 42  (coerced to a real int)
```
Real output:
```
dataclass is frozen: FrozenInstanceError
dataclass does NOT validate: Point(x='a', y='b')
pydantic validates: int_parsing - Input should be a valid integer, unable to parse string as an integer
pydantic coerces: 42 int
```
| | `dataclass` | Pydantic `BaseModel` |
|---|---|---|
| Validates input | ❌ | ✅ |
| Converts types (`"42"` → `42`) | ❌ | ✅ |
| Speed / weight | tiny | a bit heavier |
| Use it for | **trusted** internal data | **untrusted** data crossing a boundary |

In this repo: HTTP request bodies, contract DTOs, events and settings are Pydantic (they come from outside the process). Inside the domain, small value objects can be plain dataclasses.

> ⚠️ **Trap — assuming a type hint validates.** `age: int` on a dataclass accepts `"abc"`. Only Pydantic checks at runtime.

## 1.3 `Protocol` — "anything that looks like this is fine"

```python
from typing import Protocol

class Clock(Protocol):
    def now(self) -> float: ...

class GoodClock:
    def now(self) -> float: return 1.0

class BadClock:
    def time(self) -> float: return 1.0        # wrong method name

def use(clock: Clock) -> float:
    return clock.now()

use(GoodClock())     # fine
use(BadClock())      # mypy: error
```
`uv run mypy --strict file.py` says (real):
```
file.py:14: error: Argument 1 to "use" has incompatible type "BadClock"; expected "Clock"  [arg-type]
Found 1 error in 1 file (checked 1 source file)
```
`GoodClock` never says "I implement `Clock`" — it just has a matching method. That *structural* typing is how an in-process object and an HTTP client can both satisfy the same contract
([A1 · 03](../phase-a1/03-boundaries-contracts-and-layers.md)). Our real `Clock` is in [`platform_core/clock.py`](../../../libs/platform_core/src/platform_core/clock.py).

## 1.4 `async` / `await` — waiting without wasting time

A web server spends most of its time **waiting** (for the database, another service). `async def` lets one process serve other requests during those waits.

```python
import asyncio, time

async def fetch(name, secs):
    await asyncio.sleep(secs)           # "I'm waiting; let others run"
    return name

# one after another
r = [await fetch("a", .2), await fetch("b", .2), await fetch("c", .2)]
# all at once
r = await asyncio.gather(fetch("a", .2), fetch("b", .2), fetch("c", .2))
```
```
sequential awaits: 0.60s ['a', 'b', 'c']
asyncio.gather:    0.20s ['a', 'b', 'c']
calling an async def returns: coroutine
```
(To run these as a script, put the `await` lines inside `async def main():` and finish with `asyncio.run(main())`.)

Three rules that explain 90 % of async bugs:

1. **Calling `async def f()` does not run it** — it returns a *coroutine* object. You must `await` it (or give it to the event loop).
2. **`await` is a place where other tasks may run.** Between two awaits your code is *not* interrupted.
3. **Never block the event loop.** A normal `time.sleep(...)`, a slow CPU loop, or a blocking library call freezes *every* request:

```python
async def blocker(): time.sleep(.3)          # BLOCKS the whole loop
# a ticker that should fire every 0.05 s while this runs:
gaps: [0.3, 0.05, 0.05, 0.05]                # the first tick was delayed 300 ms!
```
> ⚠️ **Trap — a blocking call inside `async def`.** It "works" in a demo and ruins latency under load. Use the async version (`asyncio.sleep`, an async DB driver, `httpx.AsyncClient`) or push the blocking work to a thread (`asyncio.to_thread`). This is why password hashing (CPU-heavy) will be run in an executor when we build Auth.

## 1.5 Context managers — "set up, run, always clean up"

```python
from contextlib import contextmanager

@contextmanager
def transaction(log):
    log.append("BEGIN")
    try:
        yield                                  # <- the body of the `with` block runs here
    except Exception:
        log.append("ROLLBACK"); raise
    else:
        log.append("COMMIT")

with transaction(log): pass
with transaction(log): raise RuntimeError("boom")      # (caught outside)
print(log)
```
```
['BEGIN', 'COMMIT', 'BEGIN', 'ROLLBACK']
```
`with` guarantees the cleanup runs **even if the body raises**. Our **unit of work** is exactly this idea in async form: `async with uow_factory() as uow: ... await uow.commit()` —
leaving the block without committing rolls back ([`uow.py` template](../../../tools/templates/service/service/src/__service___service/infrastructure/db/uow.py.tmpl)).

## 1.6 Decorators — wrap a function with extra behaviour

```python
def timed(fn):
    async def wrapper(*a, **k):
        t = time.perf_counter()
        result = await fn(*a, **k)
        print(f"{fn.__name__} took {time.perf_counter()-t:.2f}s")
        return result
    return wrapper

@timed                       # same as: slow = timed(slow)
async def slow(): await asyncio.sleep(.1); return "done"
```
```
slow took 0.10s
done
```
Our `@traced_use_case` and `@traced_contract_call` ([`tracing.py`](../../../libs/platform_observability/src/platform_observability/tracing.py)) do the same: wrap a use case so a **span** (timed step in a trace) is
opened before and closed after — without the use case knowing anything about tracing.

> 💡 **Learning Thought — decorators add *cross-cutting* concerns (timing, tracing, retries, auth) without polluting business code.**

## 1.7 Generics — one definition, many types

Python 3.12 has a short syntax:

```python
class Box[T]:
    def __init__(self, item: T) -> None: self.item = item
    def get(self) -> T: return self.item

print(Box(5).get(), Box("x").get())          # 5 x     (mypy knows the first is int, the second str)
```
You've already met generics: `Page[T]` in [`pagination.py`](../../../libs/platform_core/src/platform_core/pagination.py) and `Container.bind[T](port: type[T], provider: T)` in
[`container.py`](../../../libs/platform_core/src/platform_core/container.py) — the signature promises "if you bind a `Clock` port, you must pass something that is a `Clock`".

## 1.8 Where each idea shows up in the repo

| Concept | Real example |
|---|---|
| Type hints, `mypy --strict` | everywhere; `make typecheck` |
| Pydantic | `platform_events/events.py` (`IntegrationEvent`), `platform_core/settings.py` |
| `Protocol` | `Clock`, `EventBus`, `OutboxStore`, `UnitOfWork`, `<Name>Api` contracts |
| `async`/`await` | the whole request path, `OutboxRelay`, `ServiceHttpClient` |
| Context managers | `async with uow:`; `start_span(...)`; `app_service_scope(...)` |
| Decorators | `@traced_use_case`, `@traced_contract_call`, FastAPI `@router.get` |
| Generics | `Page[T]`, `Container.bind[T]`, `traced_use_case[**P, R]` |

## 🧪 Labs
1. Change `transaction()` so a successful block appends `"COMMIT"` but a failing one appends `"ROLLBACK"` **without** re-raising. What breaks for the caller? Why is `raise` important?
2. Write a `Protocol` called `Notifier` with `async def send(self, to: str, text: str) -> None`, two implementations (`ConsoleNotifier`, `FakeNotifier` that stores messages in a list) and a function that accepts any `Notifier`. Run mypy on it.
3. Make `asyncio.gather` take 0.6 s again by changing exactly one thing. (Hint: §1.4 rule 3.)
<details><summary>Solutions</summary>

1. The caller would never learn the block failed — errors would be silently swallowed. Re-raising keeps the failure visible while still cleaning up. 2. Both classes just need a matching `send`; `FakeNotifier.messages: list[tuple[str, str]]` makes assertions easy in tests. 3. Replace `await asyncio.sleep(secs)` with `time.sleep(secs)` inside `fetch` — every "concurrent" task now blocks the loop in turn.
</details>

## 🎯 Interview Questions
1. **What does `await` actually do?** *It suspends the current coroutine and hands control back to the event loop until the awaited operation completes; other tasks can run meanwhile. It does not create a thread.*
2. **Why is `time.sleep` inside an `async def` a bug?** *It blocks the single event-loop thread, stalling all other requests; use `asyncio.sleep` or offload to a thread.*
3. **Pydantic model vs dataclass — when do you choose each?** *Pydantic for untrusted/external data needing validation and coercion; dataclass for lightweight trusted internal structures.*
4. **What is structural typing and why does `Protocol` help testing?** *A type matches if it has the right members, without inheritance. Tests can pass a tiny fake that satisfies the protocol, no mocking framework required.*
5. **What does a context manager guarantee that try/finally written by hand doesn't?** *Nothing more in behaviour, but it packages the guarantee in one reusable place so callers can't forget the cleanup.*

## ✅ Self-check
- [ ] I can explain why `double("ab")` runs and what would catch it.
- [ ] I can say which of dataclass/Pydantic validates, and where we use each.
- [ ] I can explain the three async rules and give an example of blocking the loop.
- [ ] I can read `async with uow_factory() as uow:` and say what happens on an exception.

## 📚 Further reading
- Python docs — `typing`: <https://docs.python.org/3/library/typing.html>
- Python docs — `asyncio`: <https://docs.python.org/3/library/asyncio.html>
- Pydantic — *Why use Pydantic*: <https://docs.pydantic.dev/latest/why/>
- PEP 695 — Type parameter syntax: <https://peps.python.org/pep-0695/>
- mypy cheat sheet: <https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html>

**Next:** [F · 02 — HTTP and FastAPI basics →](02-http-and-fastapi-basics.md)
