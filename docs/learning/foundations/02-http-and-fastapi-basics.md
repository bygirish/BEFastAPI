# F · 02 — HTTP and FastAPI Basics

**Goal:** understand what an HTTP request/response is, read a FastAPI route, and recognise where each FastAPI feature (validation, dependencies, middleware, lifespan) appears in our code.
**Prerequisites:** [F · 01](01-python-for-this-codebase.md). **Time:** 1 hour.
We run a 50-line demo app (shown below) and use `curl`; every response is real.

---

## 2.1 HTTP in two minutes

A client sends a **request**; the server sends back a **response**.

```
GET /items/1 HTTP/1.1            ← method  + path + version
Host: localhost:18100            ← headers (metadata)
X-Request-ID: abc                ←
                                 ← blank line
(optional body — JSON for POST)

HTTP/1.1 200 OK                  ← status code
content-type: application/json   ← response headers
                                 ←
{"id":1,"name":"apple"}          ← response body
```
| Method | Meaning | Safe to retry? |
|---|---|---|
| `GET` | read | yes |
| `POST` | create / perform an action | **no** (could create twice) — needs an idempotency key |
| `PUT` | replace | yes |
| `PATCH` | partial update | usually |
| `DELETE` | remove | yes |

| Status | Meaning | Who made the mistake? |
|---|---|---|
| `200 OK`, `201 Created`, `204 No Content` | success | — |
| `400/422` | request is invalid | **caller** |
| `401` | not authenticated | caller |
| `403` | authenticated but not allowed | caller |
| `404` | no such thing | caller |
| `409` | conflicts with current state | caller |
| `429` | too many requests | caller |
| `500` | our bug | **us** |
| `503/504` | dependency down / timed out | us (or the dependency) |

> 💡 **Learning Thought — 4xx means "you", 5xx means "us".** That split matters everywhere: dashboards count only 5xx as *errors* for our SLO, and a span is marked failed only for 5xx-type problems
> ([A1 · 06](../phase-a1/06-observability-for-beginners.md)).

## 2.2 A complete FastAPI app (try it)

Save as `mini_app.py` and run `uv run uvicorn mini_app:app --port 18100`:

```python
import time
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

ITEMS: dict[int, str] = {1: "apple", 2: "pear"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("startup: connect to things")
    yield
    print("shutdown: flush and close")

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def add_timing(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)          # everything inside runs here
    response.headers["x-process-time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    return response

class ItemIn(BaseModel):
    name: str = Field(min_length=2)
    qty: int = Field(gt=0)

class ItemOut(BaseModel):
    id: int
    name: str

def get_store() -> dict[int, str]:               # a dependency: FastAPI calls it for us
    return ITEMS
Store = Annotated[dict[int, str], Depends(get_store)]

@app.get("/items/{item_id}", response_model=ItemOut)
async def read_item(item_id: int, store: Store, verbose: bool = False) -> ItemOut:
    if item_id not in store:
        raise HTTPException(status_code=404, detail="no such item")
    return ItemOut(id=item_id, name=store[item_id])

@app.post("/items", status_code=201, response_model=ItemOut)
async def create_item(body: ItemIn, store: Store) -> ItemOut:
    new_id = max(store) + 1
    store[new_id] = body.name
    return ItemOut(id=new_id, name=body.name)
```

▶ **Try it** — five requests (real output, trimmed to status line, selected headers and body):

```
$ curl -i localhost:18100/items/1
HTTP/1.1 200 OK
content-type: application/json
x-process-time-ms: 1.9
{"id":1,"name":"apple"}

$ curl -i localhost:18100/items/99
HTTP/1.1 404 Not Found
{"detail":"no such item"}

$ curl -i localhost:18100/items/abc
HTTP/1.1 422 Unprocessable Entity
{"detail":[{"type":"int_parsing","loc":["path","item_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"abc"}]}

$ curl -i -X POST localhost:18100/items -H 'content-type: application/json' -d '{"name":"fig","qty":3}'
HTTP/1.1 201 Created
{"id":3,"name":"fig"}

$ curl -i -X POST localhost:18100/items -H 'content-type: application/json' -d '{"name":"x","qty":0}'
HTTP/1.1 422 Unprocessable Entity
{"detail":[{"type":"string_too_short","loc":["body","name"],"msg":"String should have at least 2 characters",...},
           {"type":"greater_than","loc":["body","qty"],"msg":"Input should be greater than 0",...}]}
```
Look at what you did **not** write: no code parses `abc` as an integer, no code checks `qty > 0`. You declared types and constraints; **FastAPI + Pydantic generate the validation and the 422 error for free**.

## 2.3 The five FastAPI ideas, mapped to our repo

| Idea | In the demo | In this repo |
|---|---|---|
| **Routing** — URL + method → function | `@app.get("/items/{item_id}")` | `services/<n>/service/src/<n>_service/api/v1/router.py` |
| **Validation** — types/constraints become checks | `item_id: int`, `Field(gt=0)` | request/response models in `api/v1/schemas.py` |
| **Dependency injection** — `Depends(...)` | `Store = Annotated[…, Depends(get_store)]` | `api/deps.py` (`PingUseCase`, `CurrentPrincipal`) — the **only** layer allowed to use `Depends` (rule L-6) |
| **Middleware** — code around every request | `add_timing` | [`ObservabilityMiddleware`](../../../libs/platform_observability/src/platform_observability/middleware.py): request id, `app.service`, access log, latency metric |
| **Lifespan** — start-up/shut-down | `lifespan()` | [`create_application`](../../../libs/platform_http/src/platform_http/compose.py): start relays, run `on_startup`, flush telemetry |

## 2.4 What we changed from the defaults

1. **Uniform errors.** The demo's errors look different (`{"detail": …}` vs a list). We install handlers so *every* error has one shape (`{"error": {"code", "message", "details", "request_id"}}`) —
   see [`platform_http/errors.py`](../../../libs/platform_http/src/platform_http/errors.py).
2. **Thin routes.** Real routes only parse → call one use case → return. The demo's `create_item` does business logic inline; in our repo that would live in `application/` (rule L-4).
3. **Domain errors, not `HTTPException`.** Business code raises `NotFoundError`/`InvalidInputError`; the HTTP layer converts them. Business code never imports FastAPI (rule L-2).
4. **Request ids.** Every response carries `X-Request-ID`, and the same id is on every log line.

> ⚠️ **Trap — `HTTPException` in a use case.** It welds your business rule to HTTP. A background job or event handler calling the same use case can't meaningfully return "404".

> ⚠️ **Trap — returning the ORM/database object from a route.** Always map to a response schema (rule L-5). Today's column becomes tomorrow's accidental public API.

## 2.5 ASGI in one paragraph

FastAPI doesn't speak HTTP itself. A server (**uvicorn**) speaks HTTP and calls your app through **ASGI**, a standard async interface: `await app(scope, receive, send)`. FastAPI is an ASGI app; our
`ObservabilityMiddleware` is a *pure ASGI middleware* wrapping it. Because the interface is standard, tests can call the app directly in-process (`httpx.AsyncClient(transport=ASGITransport(app=app))`) —
no network, no server — which is how all our service tests work.

## 🧪 Labs
1. Add `DELETE /items/{item_id}` returning `204` and `404` when missing. Which status code do you return for deleting something twice, and why?
2. Add a header `x-request-id` to responses in the demo's middleware (generate with `uuid.uuid4()`). How does our real middleware accept a caller-supplied id safely? (Read `ObservabilityMiddleware`.)
3. Send `curl -i localhost:18100/items/1 -X POST`. Which status do you get, and what does it teach about routing?
<details><summary>Solutions</summary>

1. Either 404 (honest: it's gone) or 204 (idempotent: the end state is what the caller wanted) — pick one and document it; we prefer 404 for clarity unless idempotent deletes are required. 2. It only accepts ids matching `[A-Za-z0-9._:-]{8,128}` and otherwise generates a UUIDv7, so a client can't inject junk into logs. 3. `405 Method Not Allowed` — the path exists, the method doesn't.
</details>

## 🎯 Interview Questions
1. **PUT vs POST vs PATCH?** *POST creates/acts (not idempotent); PUT replaces a resource (idempotent); PATCH applies a partial change.*
2. **Why do we return 422 for invalid bodies and 5xx only for our bugs?** *4xx signals caller error (not retried, not counted against our SLO); 5xx signals server failure (retry, alert).*
3. **What is dependency injection in FastAPI and why do we confine `Depends` to `api/`?** *`Depends` declares what a route needs and FastAPI supplies it per request. Confining it to `api/` keeps use cases framework-free and reusable from jobs/handlers.*
4. **What does a middleware see that a route doesn't?** *Every request and response, including those that never match a route (404s) and errors — ideal for request ids, logging and metrics.*
5. **How do you test a FastAPI app without starting a server?** *Call it through an ASGI transport in-process (`httpx.AsyncClient(transport=ASGITransport(app=app))`).*

## ✅ Self-check
- [ ] I can write the first lines of an HTTP request and response and name 5 status codes with who's at fault.
- [ ] I can explain where validation errors come from in the demo.
- [ ] I can point at the five FastAPI ideas in our repo.
- [ ] I can explain why routes are thin and business code doesn't use `HTTPException`.

## 📚 Further reading
- FastAPI tutorial: <https://fastapi.tiangolo.com/tutorial/>
- MDN — HTTP overview: <https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview>
- MDN — HTTP response status codes: <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status>
- ASGI specification: <https://asgi.readthedocs.io/en/latest/>

**Next:** [F · 03 — Databases for backend developers →](03-databases-for-backend-developers.md)
