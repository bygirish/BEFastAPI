# 06 · Observability for Beginners

**Goal:** understand logs, metrics and traces, why we link them, and how this repo emits them — including a real bug we caught.
**Prerequisites:** chapter 05. **Time:** 1 hour.

> **Observability** = being able to ask new questions about a running system *without shipping new code*. You can't debug what you can't see.

---

## 6.1 Three signals, three questions

| Signal | Shape | Answers | Cost | Example |
|---|---|---|---|---|
| **Metrics** | numbers over time | *Is something wrong? How bad?* | cheap | "5xx rate is 2 %" |
| **Traces** | a tree of timed steps for **one** request | *Where did the time go?* | medium | "the DB call took 800 ms" |
| **Logs** | discrete events with details | *What exactly happened?* | highest | "login_failed reason=locked" |

Typical flow: an **alert** (metric) → open a slow **trace** → read its **logs**. That jump only works if the three share an identifier.

> 💡 **Learning Thought — correlation is the feature.** Three separate tools are an archaeology dig. Three tools sharing `trace_id` are a
> debugger. Every log line here carries `trace_id`, and latency metrics can carry *exemplars* (a sample trace id).

## 6.2 What we built (Phase A1)

```
your code ──► OpenTelemetry API ──► SDK ──► OTLP ──► Collector ──► Tempo (traces) · Prometheus (metrics) · Loki (logs) ──► Grafana
 (A1: done)                                              └── (Phase A2: the containers that run all this)
```
Phase A1 delivers everything **left of the Collector** (inside `libs/platform_observability`). Phase A2 adds the containers.

| Concern | Where | Notes |
|---|---|---|
| JSON logs, redaction, request/trace correlation | `logging.py`, `redaction.py`, `context.py` | structlog on top of Python's `logging`, so third-party logs are captured too |
| Request id, `app.service`, access log, latency metric | `middleware.py` | `X-Request-ID` in and out |
| Spans for use cases and cross-service calls | `tracing.py` | `@traced_use_case`, `@traced_contract_call` |
| Business metrics with guard-rails | `metrics.py` | allow-listed attributes |
| Health endpoints | `health.py` | `/livez` `/readyz` `/startupz` |
| SDK/exporter bootstrap | `setup.py` | the **only** file touching the SDK (rule O-1) |
| In-memory telemetry for tests | `testing.py` | assert on spans/metrics in unit tests |

### The identity trick: `app.service`
Everything runs in *one* process, so OpenTelemetry's `service.name` would be the same for Auth and Users. We add our own attribute
`app.service` (`auth`, `users`…) to **every** signal. Dashboards and alerts filter on it, so **they keep working unchanged after a service is extracted** (rule O-7).

## 6.3 Logging rules, with examples

```python
log.info("login_failed", reason="locked", method="password")        # ✅ constant event name + data in fields
log.info(f"user {email} failed to log in")                          # ❌ variable message: can't search, leaks PII
```
- One JSON object per line to stdout. `event` is a **constant** string; variable data goes into fields.
- **Log once, at the boundary** (HTTP error handler, job runner). Don't `log + raise` at every layer — you'd get five copies of one error (rule O-3).
- Never log passwords, OTPs, tokens, full e-mails/phones. A redaction processor removes known-sensitive keys and token-shaped strings even if you forget (rule O-4).

## 6.4 Metrics rules: the cardinality trap

Every distinct combination of label values is a **separate time series** stored forever.

| Label | Distinct values | Verdict |
|---|---|---|
| `outcome` ∈ {ok, locked, error} | 3 | ✅ |
| `method` ∈ {password, otp, google} | 3 | ✅ |
| `user_id` | millions | ❌ would create millions of series |
| raw URL `/users/123/orders/9` | unbounded | ❌ use the route *template* `/users/{id}/orders/{oid}` |

So each metric declares its allowed attributes up front:

```python
LOGINS = Counter("auth.login.attempts",
                 allowed={"method": frozenset({"password", "otp", "google"}), "outcome": None})
LOGINS.add(method="password", outcome="ok")     # fine
LOGINS.add(user_id="u-1")                       # raises MetricAttributeError locally/in tests; dropped in production
```
Strict locally (so you notice), lenient in production (so a typo never takes the service down).

## 6.5 A real bug story — the double-counted metric

While capturing output for chapter 05 we printed the metric points for one request and saw **two** series with the same name:

```
http.server.request.duration  {url.scheme: http, http.request.method: GET, network.protocol.version: 1.1, http.route: ..., status: 200}
http.server.request.duration  {http.request.method: GET, http.route: ..., status: 200, app.service: demo}
```
**Cause:** the FastAPI version we run now ships *its own* OpenTelemetry support. It emitted one request-duration metric (without `app.service`)
and our middleware emitted another. Dashboards that `sum()` the metric would count every request twice.

**Fix** (in `create_application`): keep FastAPI's native **spans**, turn its **metrics and logs off** (`telemetry={"metrics": False, "logs": False, ...}`), and
drop the older contrib instrumentor. **Regression test:** `apps/monolith/tests/test_composition.py::test_one_server_span_and_no_duplicate_request_metric`
asserts exactly one SERVER span and that every request-duration point carries `app.service`.

> 💡 **Learning Thought — look at the raw data once.** The unit tests were green. Only *looking at the actual emitted points* revealed the duplicate.
> When you add instrumentation, print what it emits at least once.

> ⚠️ **Trap — two libraries each "helpfully" instrument the same thing.** Symptoms: duplicate spans, doubled counters. Decide who owns
> each signal and switch the other off.

## 6.6 Testing telemetry

```python
from platform_observability import testing as obs_testing
telemetry = obs_testing.install()            # in-memory exporters (installed once per process)
...make a request...
assert "demo.Ping" in telemetry.span_names()
assert any(p.get("app.service") == "demo" for p in telemetry.data_points("http.server.request.duration"))
```
> ⚠️ **Trap — `OTEL_SDK_DISABLED=true` makes tests see zero spans.** It turns the SDK into a no-op. Our scaffold check failed once because a
> script exported that variable; the spans list was `[]`. Don't set it when you assert on telemetry.

## 🧪 Lab 6.1
1. Add a counter `notes.created` allowing only `source ∈ {api, import}`. Call it with `source="email"` and watch it raise. 
2. Write a log call that would leak a password into logs and show that the output contains `[REDACTED]`.
<details><summary>Solution</summary>

1. `Counter("notes.created", allowed={"source": frozenset({"api","import"})}).add(source="email")` → `MetricAttributeError: Value 'email' not allowed for attribute 'source'`.
2. `log.info("x", password="hunter2")` → the JSON line has `"password": "[REDACTED]"` (see `libs/platform_observability/tests/test_redaction_and_logging.py`).
</details>

## 🎯 Interview Questions
1. **Logs vs metrics vs traces — when do you reach for each?** *Metrics to detect and alert, traces to localize latency/failure across steps, logs for exact detail. Link them with a shared trace id.*
2. **What is metric cardinality and why does it matter?** *Number of distinct label combinations; each is a stored series. Unbounded labels (ids, URLs) blow up cost and query speed.*
3. **Why OpenTelemetry instead of a vendor agent?** *A vendor-neutral standard: swap backends by changing the Collector, not application code.*
4. **Why log structured JSON with a constant event name?** *Machine-searchable and aggregatable; free-text messages can't be reliably queried and tend to embed sensitive data.*
5. **What does `app.service` buy us?** *Stable per-service dashboards/alerts that survive extraction, even though `service.name` changes.*

## ✅ Self-check
- [ ] I can explain the three signals and give an example question for each.
- [ ] I can say why `user_id` must not be a metric label.
- [ ] I can explain the double-counting bug and its fix in two sentences.
- [ ] I know where redaction happens and why it is automatic.

## 📚 Further reading
- OpenTelemetry — Concepts: <https://opentelemetry.io/docs/concepts/>
- OpenTelemetry — Python: <https://opentelemetry.io/docs/languages/python/>
- structlog: <https://www.structlog.org/>
- Google SRE Workbook — Alerting on SLOs: <https://sre.google/workbook/alerting-on-slos/>

**Next:** [07 · Adding a service (hands-on) →](07-adding-a-service-hands-on.md)
