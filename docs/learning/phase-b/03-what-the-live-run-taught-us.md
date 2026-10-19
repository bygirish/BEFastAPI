# B · 03 — What the Live Run Taught Us

**Goal:** learn from the eight real problems found while building and running Notifications — each one passed code review *in the author's head* and was caught only by a test, the linter, or the live stack — and see the regression test that now guards each.
**Prerequisites:** [B · 01](01-notifications-concepts-and-design.md), [B · 02](02-hands-on-live-stack.md). **Time:** 40 min.

> These are the most valuable pages in the phase. Every item has the real symptom, the cause, the fix and the test that keeps it fixed. If you only have ten minutes, read **P4** and **P5** — they are about *metrics lying to you*, which is the most expensive kind of bug in operations.

| # | Problem | Found by | Guarded by |
|---|---|---|---|
| P1 | A `503` from Notifications lost its error body over HTTP | contract test (HTTP variant) | `test_exhausted_retryable_status_keeps_the_remote_error_body` |
| P2 | Dev endpoint defaulted to OTP variables for *every* template | live run | `test_dev_send_fills_sample_variables_for_every_builtin_template` |
| P3 | The delivery SLO matched no data (`…_total`) | live run (Prometheus) | `test_counter_ratio_requires_the_prometheus_total_suffix` |
| P4 | New counter series were invisible to `rate()` | live run (SLO ratio `0` / `NaN`) | `test_priming_creates_a_series_nothing_else_has_touched` |
| P5 | In-process contract calls were attributed to the *caller* | design review → test | `test_in_process_calls_are_attributed_to_the_notifications_service` |
| P6 | Tests could not `import conftest` | first test run | helpers live in `notifications_service/testing.py` |
| P7 | Lint: mutable defaults in settings | `ruff` (RUF012) | the linter itself |
| P8 | A running Prometheus never loaded the new service's SLO rules | final `make stack-check` on a stack that was already up | `stack_check.sh`, `make up` and `demo.sh` now send SIGHUP |

---

## P1 · The HTTP client threw away the error body of a `503`

**Symptom.** The contract tests run the same assertions against the in-process implementation and the HTTP client (see B · 01 §1.4). Every test passed for `in_process`; the `http` variant of the "total failure" test failed: the in-process error carried `details["delivery_id"]`, the HTTP one did not.

**Cause.** When all providers fail, the service answers `503` with a perfectly good body (`NOTIFICATIONS_ALL_PROVIDERS_FAILED`, `delivery_id`). But the shared `ServiceHttpClient` treats `502/503/504` as "retryable transport-ish failures" and, when it stops retrying, raised a generic `UnavailableError("<target> returned 503")` — **dropping the body**. The two implementations of one contract disagreed.

**Fix.** The platform client now keeps the remote service's own error object in `details["remote_error"]` (plus `status`), and `NotificationsHttpClient` re-raises `NotificationsUnavailable` with the remote `code` and `details` ([`http_client.py`](../../../services/notifications/contracts/src/notifications_contracts/http_client.py) `_unavailable`).

```python
# libs/platform_http/src/platform_http/client.py (excerpt)
last_error = UnavailableError(
    f"{self._target} returned {response.status_code}",
    details={"target": self._target, "status": response.status_code, "remote_error": _remote_error(response)},
)
```

> 💡 **Learning Thought — contract tests earn their keep at the *edges of failure*.** Happy paths agree trivially. It was the unhappy path (a specific error with details) where "in-process" and "over HTTP" quietly diverged, and divergence is exactly what breaks a service the day it is extracted.

## P2 · The dev endpoint broke every template except `otp`

**Symptom (live).** Hitting the dev route with `"template":"password_changed"` and no variables:
```
{"error":{"code":"NOTIFICATIONS_TEMPLATE_VARIABLES", ... "details":{"template":"password_changed","missing":[],"unexpected":["code","ttl_minutes"]}}}
```
**Cause.** The request model defaulted `variables` to `{"code": "123456", "ttl_minutes": "5"}` — right for `otp`, "unexpected" for the others (templates require an *exact* match).

**Fix.** `variables` is optional; when omitted the router picks sample values **per template** (`SAMPLE_VARIABLES`). Regression test loops over *every* built-in template, so adding a template without samples fails loudly.

## P3 · The SLO query matched nothing: `notifications_delivery` vs `notifications_delivery_total`

**Symptom (live).** The "attempts by provider" query returned an empty result, and the metric name list showed:
```
['notifications_delivery_total', 'notifications_provider_attempt_total', ...]
```
while `slo.yaml` said `metric: notifications_delivery`. A query for a metric that doesn't exist is **not an error in Prometheus** — it silently returns "no data", so the alert would simply never fire.

**Cause.** The OTel → Prometheus path appends `_total` to counters (and `_seconds_bucket/_count/_sum` to histograms). The code defines `notifications.delivery`; the Prometheus name differs.

**Fix.** `slo.yaml` uses `notifications_delivery_total`, **and** the generator now refuses a `counter_ratio` metric that doesn't end in `_total` ([`sync_observability.py`](../../../tools/sync_observability.py)), so the next person gets an error at generation time instead of silence at 3 a.m.

> ⚠️ **Trap — "no error" is not "working".** Whenever you write a query, alert or dashboard, run it once against real data and look at a non-empty result. An empty result is the usual sign of a misspelt name.

## P4 · New counter series are invisible to `rate()`

**Symptom (live).** After 3 failed deliveries in a freshly started process, the burn-rate expression returned `0`, then `NaN`; `increase(notifications_delivery_total[5m])` said `failed 0` although three `503`s had just been served.

**Cause.** `rate()` and `increase()` compute from the *difference between consecutive samples*. A series that appears for the first time **already at 3** (or at 1 — your very first failure ever) has no earlier sample, so the jump from "nothing" to 3 is invisible. The very events an SLO exists to catch — the first failures — are the ones it can't see.

**Fix.** Our label values are closed sets, so we know every series in advance. At start-up `prime_metrics()` ([`telemetry.py`](../../../services/notifications/service/src/notifications_service/application/telemetry.py)) increments each one by **0**, publishing them all at zero before any traffic. After the fix the same experiment (4 failures + 4 successes) gave the ratio `0.5` (B · 02 §2.10).

```python
for channel in _CHANNELS:
    for outcome in _DELIVERY_OUTCOMES:
        DELIVERIES.add(0, channel=channel, outcome=outcome)
```

> 💡 **Learning Thought — closed label sets (rule O-5) pay a second dividend.** We introduced them to stop cardinality explosions; they also let us pre-create every series. With free-text labels you can't, and "first failure is invisible" stays true forever.

## P5 · In-process calls were attributed to the wrong service

**Symptom (found while designing the template).** When Auth (later) calls `NotificationsApi.send(...)` *in the same process*, the code runs inside Auth's request. The telemetry context therefore said `app.service = auth`, so Notifications' spans would be named `auth.SendNotification` and its metrics labelled `auth` — dashboards and the delivery SLO (which filters on `app_service="notifications"`) would be wrong, **and would silently change** the day you extract the service to its own process.

**Fix.** The in-process contract implementation re-scopes the context ([`contracts_impl.py`](../../../services/notifications/service/src/notifications_service/contracts_impl.py)):

```python
@traced_contract_call(_CONTRACT)
async def send(self, request: SendRequest) -> SendResult:
    with app_service_scope("notifications"):
        return await self._send(request)
```
This was added to the **generator template** too, so every future service gets it. The test calls the contract from outside any request and asserts the span is named `notifications.SendNotification` and is *not* `app.SendNotification`.

## P6 · `ModuleNotFoundError: No module named 'conftest'`

**Symptom.** First run of the new tests:
```
services/notifications/service/tests/test_contract.py:10: in <module>
    from conftest import Harness, MakeHarness, otp
E   ModuleNotFoundError: No module named 'conftest'
```
**Cause.** The repo uses pytest's `importlib` import mode (so identically named test files in different services can't collide). In that mode `conftest.py` is **not** importable as a module — pytest loads it for *fixtures* only.

**Fix.** Plain helper code (`Harness`, `otp`) moved into the package as [`notifications_service/testing.py`](../../../services/notifications/service/src/notifications_service/testing.py) — the same pattern as `platform_security.testing` — and only fixtures remain in `conftest.py`.

## P7 · Lint: `RUF012 Mutable default value for class attribute`

```
RUF012 Mutable default value for class attribute
  --> services/notifications/service/src/notifications_service/settings.py:23:53
23 |     sms_providers: Annotated[list[str], NoDecode] = ["console"]
```
A list literal as a class-level default is shared by every instance. In a settings class use `Field(default_factory=lambda: ["console"])`. (Related trap in the same field: `pydantic-settings` tries to parse a `list[str]` environment variable as **JSON**, so `smtp,console` would raise a decoding error — hence `NoDecode` plus a small validator that splits on commas.)

> ⚠️ **Bonus trap (avoided by design, not by luck) — SQLite hands back naive datetimes; PostgreSQL hands back aware ones.** The tests run on SQLite, production on PostgreSQL. The repository normalises with `_utc()` ([`repository.py`](../../../services/notifications/service/src/notifications_service/infrastructure/db/repository.py)). Without it the rate-limit arithmetic would be `aware − naive`, which Python rejects: `TypeError: can't subtract offset-naive and offset-aware datetimes` — and only on one of the two databases.

## P8 · Prometheus doesn't notice new rule files

**Symptom.** The final `make stack-check` — run on a stack that had been up for a while — passed six of seven checks and failed the last:
```
FAIL  Alertmanager ready + SLO rules loaded    LookupError: group stackcheck-slo not loaded; have ['notifications-slo', 'platform']
```
**Cause.** `make obs-sync` wrote `stackcheck.slo.rules.yml` into the mounted folder, but Prometheus reads rule files at start-up and on *reload*; it does not watch the directory. A fresh stack hides this (it starts after the files exist), a long-running one does not.

**Fix.** After `docker compose up`, send `SIGHUP` (`docker compose kill -s HUP prometheus`) — Prometheus re-reads its configuration and rules without restarting. `make up`, `make stack-check` and `tools/demo.sh` do it; the manual command is in [troubleshooting #40](../troubleshooting.md). Re-running the check on an already-running stack then passed 7/7.

> 💡 **Learning Thought — test the *dirty* path, not only the clean one.** Most developers have a stack that has been up for days. A check that only works from a pristine state is a check that passes in CI and fails on laptops.

## 🧪 Labs
1. **Reproduce P4.** In [`module.py`](../../../services/notifications/service/src/notifications_service/module.py) comment out the `prime_metrics(...)` call, rebuild (`docker compose up -d --build --wait app`), restart the outage override from B · 02 §2.9, send 3 failing emails, wait 40 s and run the `increase(notifications_delivery_total{outcome="failed"}[5m])` query. What do you see? Restore the line and repeat.
2. **Reproduce P3 safely.** Temporarily change `metric:` in `services/notifications/observability/slo.yaml` to `notifications_delivery` (revert afterwards) and run `uv run python tools/sync_observability.py`. What happens now, and why is that better than before?
3. **Write the test first.** Imagine a new template `login_alert` is added to `TEMPLATES` but not to `SAMPLE_VARIABLES`. Which existing test fails, and with what message?
4. **Spot the divergence.** Add a new contract error `NotificationsBlocked` raised in-process only. Which test in `test_contract.py` would you extend to catch the HTTP client not mapping it?

<details><summary>Solutions</summary>

1. Without priming, `increase(...{outcome="failed"})` reports `0` (or no series) even though the app answered three `503`s. After restoring the line, the same experiment shows a positive number. The point: the failure was real, the metric didn't show it.
2. The generator stops with `ObservabilityError: notifications: counter_ratio metric must be the Prometheus counter name ending in _total, got 'notifications_delivery'`. Failing at *generation* time beats an alert that never fires.
3. `test_dev_send_fills_sample_variables_for_every_builtin_template` — the dev endpoint answers `422` for `login_alert` (missing `device`), and the assertion message names the template.
4. `test_errors_are_the_same_types_in_both_implementations` is parametrised over `in_process` and `http`; add an assertion for the new error there, and map its status code in `http_client._raise_for`.
</details>

## 🎯 Interview Questions
1. **Why can a metric silently return "no data" instead of an error, and how do you defend against it?** *PromQL treats an unknown name as an empty selection. Defend by running each new query against real data once, by validating names at generation time, and by alerting on absent data for critical SLIs (`absent()`).*
2. **A counter jumps from nothing to 5 in one scrape. What does `rate()` show and why does it matter?** *Nothing for that jump — there's no earlier sample to subtract. Initialising known series to 0 at start-up (possible when label values are a closed set) fixes it.*
3. **Why do contract tests run against both the in-process and the HTTP implementation?** *So the two never drift: a caller must not be able to tell which one it got, including how failures look. P1 was a real drift.*
4. **Why does `app.service` need to be re-scoped for in-process cross-service calls?** *The call executes inside the caller's request context. Without re-scoping, telemetry is attributed to the caller and changes meaning after extraction.*
5. **Why does pytest's `importlib` mode make `from conftest import …` fail, and what is the clean alternative?** *Test files aren't importable as package modules there; share helpers via an importable module (e.g. `package.testing`) and keep only fixtures in `conftest.py`.*

## ✅ Self-check
- [ ] I can state each problem's symptom, cause and fix in one sentence.
- [ ] I know why an *empty* query result must never be read as "all good".
- [ ] I can explain priming counters to a colleague, including why `rate()` needs two samples.
- [ ] I know which test guards each problem.

## 📚 Further reading
- Prometheus — *Counters and rates (`rate()` semantics)*: <https://prometheus.io/docs/prometheus/latest/querying/functions/#rate>
- Prometheus — *Instrumentation best practices: avoid missing metrics* (initialise series at 0): <https://prometheus.io/docs/practices/instrumentation/#avoid-missing-metrics>
- OpenTelemetry — *Prometheus and OpenMetrics compatibility* (the `_total` suffix): <https://opentelemetry.io/docs/specs/otel/compatibility/prometheus_and_openmetrics/>
- pytest — *Import modes*: <https://docs.pytest.org/en/stable/explanation/pythonpath.html>

**Next:** [B · 04 — Lab: add a vendor adapter →](04-lab-add-a-vendor-adapter.md)
