# KT · 03 — Design Patterns Catalogue

**Goal:** a field guide to every named pattern in this repo: what problem it solves, **where to find it**, a tiny example, and *when not to use it*.
**Prerequisites:** [A1 · 03](../phase-a1/03-boundaries-contracts-and-layers.md). **Time:** 45 min (reference — dip in as needed).

> A **pattern** is a named, proven shape for a recurring problem. Knowing the names lets you say "this is a *port and adapter*" in a review instead of re-explaining it.

| # | Pattern | One-line purpose | Primary location |
|---|---|---|---|
| 1 | Dependency Injection + Composition Root | Pass collaborators in; assemble them in one place | [`container.py`](../../../libs/platform_core/src/platform_core/container.py), [`wiring.py`](../../../apps/monolith/src/monolith_app/wiring.py) |
| 2 | Ports & Adapters (Hexagonal) | Business code talks to interfaces you own | `application/ports.py`, `infrastructure/clients/` |
| 3 | Unit of Work | One transaction per use case | generated `infrastructure/db/uow.py` |
| 4 | Transactional Outbox | Atomically save data *and* an event | [`outbox.py`](../../../libs/platform_events/src/platform_events/outbox.py) |
| 5 | Publish / Subscribe | Announce facts; subscribers react | [`bus.py`](../../../libs/platform_events/src/platform_events/bus.py) |
| 6 | Idempotent Receiver | Handling twice == handling once | [`idempotency.py`](../../../libs/platform_events/src/platform_events/idempotency.py) |
| 7 | Facade | One simple door in front of a complex subsystem | [`module.py`](../../../libs/platform_http/src/platform_http/module.py), `platform_observability.setup()` |
| 8 | Adapter | Make one interface look like another | `SqlOutboxWriter`, `<Name>HttpClient` |
| 9 | Strategy | Swap an algorithm behind one interface | key providers in [`keys.py`](../../../libs/platform_security/src/platform_security/keys.py) |
| 10 | Decorator | Add behaviour around a function | [`tracing.py`](../../../libs/platform_observability/src/platform_observability/tracing.py) |
| 11 | Middleware (Chain of Responsibility) | Layered handlers around every request | [`middleware.py`](../../../libs/platform_observability/src/platform_observability/middleware.py) |
| 12 | Factory | Build a configured object | `create_application`, `build_engine`, `build_module` |
| 13 | Plugin / Registry (entry points) | Discover implementations without importing them | `befastapi.services` entry-point group |
| 14 | Fake / Null Object | A harmless stand-in | `InMemoryOutbox`, `FixedClock`, `StaticKeyProvider` |
| 15 | Retry with backoff + idempotency key | Survive transient failures safely | [`client.py`](../../../libs/platform_http/src/platform_http/client.py) |
| 16 | Template (scaffolding) | Generate correct-by-construction code | [`new_service.py`](../../../tools/new_service.py) |

---

## 1. Dependency Injection + Composition Root
**Problem:** a class that creates its own database connection or clock is impossible to test and impossible to swap.
**Solution:** receive collaborators through the constructor; build and connect everything in **one** place (the *composition root*).
```python
class Ping:
    def __init__(self, uow_factory, clock) -> None: ...      # collaborators come IN
# apps/monolith … wiring:  container.bind(NotesApi, NotesApiImpl(ping, shout))
```
**Don't:** use module-level singletons (`engine = create_engine(...)` at import) or let business code call `Container.resolve` itself (that's the *service locator* anti-pattern; only `api/deps.py` and wiring may resolve).

## 2. Ports & Adapters (Hexagonal)
**Problem:** Users needs avatar URLs from Files without being welded to Files.
**Solution:** Users defines `AvatarStore` (**port**, its own words); an **adapter** wraps `files_contracts.FilesApi`. Details and diagram: [A1 · 03 §3.3](../phase-a1/03-boundaries-contracts-and-layers.md).
**Don't:** create a port with one method per vendor feature "just in case" — ports describe *what you need*, not what the other side offers.

## 3. Unit of Work
**Problem:** several changes must succeed or fail together.
**Solution:** an object that owns a session/transaction: `async with uow: … await uow.commit()`; leaving without commit rolls back. See [F · 03 §3.3](../foundations/03-databases-for-backend-developers.md).
**Don't:** hold a UoW open across a network call to another service (locks and long transactions); do the call before or after.

## 4. Transactional Outbox
**Problem:** "save, then publish" can crash in between.
**Solution:** insert the event into an `outbox` table *in the same transaction*; a relay publishes it afterwards. See [A1 · 05 §5.3](../phase-a1/05-a-request-end-to-end.md).
```python
async with uow_factory() as uow:
    await uow.outbox.add(PingReceived(message="pong"))   # same transaction as any data change
    await uow.commit()
```
**Don't:** publish directly to the bus from a use case (dual-write), and don't put big payloads in events (IDs + minimal fields, rule C-6).

## 5. Publish / Subscribe
**Problem:** Auth shouldn't know who cares that a user registered.
**Solution:** publish a **fact** (`auth.user_registered.v1`); any service subscribes. Publisher and subscribers never import each other.
**Don't:** use events as hidden RPC ("publish and wait for a reply event") — if you need an answer, make a call (rule C-9).

## 6. Idempotent Receiver
**Problem:** at-least-once delivery means duplicates.
**Solution:** remember processed `(handler, event_id)` and skip repeats.
```python
bus.subscribe("auth.user_registered.v1", idempotent("users.create_profile", store, handler))
```
**Don't:** assume ordering or single delivery.

## 7. Facade
**Problem:** a subsystem with many parts (OpenTelemetry has ~15 classes) intimidates callers.
**Solution:** one function/class with a simple interface in front: `platform_observability.setup(...)`, `ServiceModule`.
**Don't:** let the facade grow knobs for everything; if every option is exposed, it's not a facade, it's a wrapper.

## 8. Adapter
**Problem:** two interfaces don't match.
**Solution:** a small class translates: `SqlOutboxWriter` makes a SQLAlchemy session look like an `OutboxWriter`; `NotesHttpClient` makes HTTP calls look like `NotesApi`.
**Don't:** put business rules in adapters — they translate, nothing more.

## 9. Strategy
**Problem:** several interchangeable ways to do one thing.
**Solution:** one interface, many implementations, chosen by configuration: `StaticKeyProvider` (tests/dev) vs `JwksKeyProvider` (production) both satisfy `KeyProvider`; later, OTP senders (SMS vendors) will too.

## 10. Decorator
**Problem:** tracing/timing/retry code would clutter every use case.
**Solution:** wrap the function — `@traced_use_case` opens a span around the call ([F · 01 §1.6](../foundations/01-python-for-this-codebase.md)).
**Don't:** stack many decorators whose order matters without documenting it.

## 11. Middleware (Chain of Responsibility)
**Problem:** every request needs the same prelude/postlude (request id, logging, metrics).
**Solution:** wrap the app in layers; each calls the next ([F · 02 §2.3](../foundations/02-http-and-fastapi-basics.md)). Order matters: ours is outermost so it also sees 404s and errors.

## 12. Factory
**Problem:** constructing a correctly-configured object takes many steps.
**Solution:** a function that does them: `create_application(...)`, `build_engine(settings)`, `build_module()`.

## 13. Plugin / Registry via entry points
**Problem:** the monolith must run "whatever services are installed" without a hard-coded list.
**Solution:** each service registers `befastapi.services` in its `pyproject.toml`; `load_modules()` discovers them ([A1 · 02 §2.5](../phase-a1/02-monorepo-and-uv.md)).

## 14. Fake / Null Object
**Problem:** tests shouldn't need real infrastructure.
**Solution:** small working stand-ins that obey the same interface: `InMemoryOutbox`, `FixedClock`, `TestAuth`. See [F · 04 §4.3](../foundations/04-testing-guide.md).

## 15. Retry with backoff + idempotency key
**Problem:** networks fail transiently; blind retries can duplicate work.
**Solution:** retry **idempotent** requests (GET/PUT/DELETE) with jittered exponential backoff; retry a POST *only* with an `Idempotency-Key`; map exhaustion to `UnavailableError`/`DependencyTimeoutError`.
**Don't:** retry forever, or retry non-idempotent calls blindly.

## 16. Template / scaffolding
**Problem:** "copy the last service and edit" copies old mistakes.
**Solution:** a generator producing a known-good skeleton, guarded by a CI scaffold check ([A1 · 08](../phase-a1/08-quality-gates-and-ci.md)).

---

## Patterns we deliberately did **not** adopt (yet) — and why
| Pattern | Why not now |
|---|---|
| Event sourcing | Adds big complexity; the outbox gives reliable events without storing state as events |
| CQRS read models | Not needed until a service needs a denormalised copy of another's data (Users, Phase D) |
| Saga / distributed transactions | We forbid cross-service transactions (rule D-6); revisit when a real multi-service workflow appears |
| Circuit breaker | Premature before real remote calls exist; retries + timeouts cover the first extraction |
| Repository per entity (full ORM) | Services are small; revisit when a service grows real domain entities |

## 🧪 Labs
1. Find one place where a pattern from this list is **violated** deliberately and justified (hint: the test-only `schema_translate_map` for SQLite). What makes it acceptable?
2. Add a second `KeyProvider` strategy that reads a PEM from an environment variable. Which file would you register it in, and which tests prove it?
3. Sketch the *adapter* the Auth service will need to send OTPs through the Notifications service. What is the port called and who owns it?
<details><summary>Solutions</summary>

1. It's confined to infrastructure (`engine.py`), controlled by the URL scheme, and exists purely so the same models run under SQLite tests. 2. In `keys.py`, with tests following `libs/platform_security/tests/test_security.py`. 3. Port `OtpDelivery` in Auth's `application/ports.py`; adapter in Auth's `infrastructure/clients/` wrapping `notifications_contracts.NotificationsApi`; binding in `apps/*/wiring.py`.
</details>

## 🎯 Interview Questions
1. **Dependency injection vs service locator?** *DI pushes dependencies in (explicit, testable); a locator pulls them out of a global registry (hidden dependencies). We allow resolution only at the edge.*
2. **How is an adapter different from a facade?** *An adapter makes one interface fit another; a facade simplifies access to a whole subsystem.*
3. **Why is the outbox a pattern and not just "a table of events"?** *Its value is the guarantee — written in the same transaction as the data — plus the relay and idempotent consumers that complete the delivery story.*
4. **When would you *not* introduce a pattern?** *When the problem hasn't appeared yet; each pattern adds indirection that must pay for itself.*

## ✅ Self-check
- [ ] I can name the pattern in any of the 16 locations above.
- [ ] I can explain one "don't" per pattern.
- [ ] I know which patterns we skipped on purpose and why.

**Next:** [KT · 04 — Architecture diagrams →](04-architecture-diagrams.md)
