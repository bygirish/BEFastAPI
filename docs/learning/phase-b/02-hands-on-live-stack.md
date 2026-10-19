# B · 02 — Hands-on: Mailpit, Failover, Idempotency, Rate Limit and an Outage

**Goal:** drive the real Notifications service on the full Docker stack and *watch* each behaviour from [B · 01](01-notifications-concepts-and-design.md) happen: delivery, failover, de-duplication, the rate cap, a total outage, and the SLO reacting to it.
**Prerequisites:** B · 01, Docker Desktop running, [A2 · 02 Compose](../phase-a2/02-compose-the-whole-system.md). **Time:** 45 min.
Everything below was run for real on `APP_PORT=18000` (port 8000 was taken on the author's machine); use your own port in the commands.

> There is no public endpoint for Notifications — users never call it; *other services* do. To let you poke it by hand, the local stack mounts a **development-only** route, `POST /api/v1/notifications/dev/send`, switched on by `NOTIFICATIONS_DEV_ENDPOINTS=true` in [`compose.env`](../../../services/notifications/service/compose.env). It is refused when `ENV=production` (rule **X-11**).

---

## 2.0 Start the stack

```bash
cp .env.example .env            # once
APP_PORT=18000 make up          # postgres, redis, migrations, app, the observability stack, Mailpit, Adminer
```
```bash
curl -s localhost:18000/readyz
```
```json
{"status":"ok","modules":[{"service":"notifications","status":"ok","checks":[{"name":"database","status":"ok","detail":null}]}]}
```
Two things happened that you didn't have to do: the `db-provision` job created the `notifications` role and schema, and the `migrate-notifications` job ran migrations `0001` (outbox) and `0002` (deliveries) — see §2.8. The email chain is `smtp,console`: **try Mailpit (a fake SMTP inbox) first, fall back to printing in the app log.** The SMS chain is `console`.

## 2.1 Send an email → it arrives in Mailpit

```bash
B=http://localhost:18000/api/v1/notifications/dev
curl -s -X POST $B/send -H 'content-type: application/json' \
  -d '{"channel":"email","recipient":"Asha@Example.com","template":"otp"}'
```
```json
{"delivery_id":"01a1537c-d127-763c-9253-90d7c4c77274","status":"sent","provider":"smtp","attempts":1}
```
Open <http://localhost:8025> (Mailpit's inbox) or ask its API:
```bash
curl -s localhost:8025/api/v1/messages
```
```
count 1
{'Subject': 'Your verification code', 'Snippet': 'Your verification code is 123456. It expires in 5 minutes. Never share it with anyone.'} asha@example.com no-reply@befastapi.local
```
Notice `Asha@Example.com` arrived as `asha@example.com` — recipients are **normalised** before anything else (which is also what makes the rate cap fair).

## 2.2 Send an SMS → the console provider prints it

```bash
curl -s -X POST $B/send -H 'content-type: application/json' \
  -d '{"channel":"sms","recipient":"+1 (415) 555-0123","template":"otp"}'
docker compose logs --no-color app | grep -E 'console_message|delivery_sent' | tail -2
```
```
{"delivery_id": "01a1537c-d1e2-753b-b48b-803204cfd7f1", "status": "sent", "provider": "console", "attempts": 1}
{"channel": "sms", "to": "+14155550123", "subject": null, "message_body": "Your verification code is 123456. It expires in 5 minutes. Never share it with anyone.", "event": "console_message", ...}
{"delivery_id": "01a1537c-d1e2-753b-b48b-803204cfd7f1", "channel": "sms", "provider": "console", "attempts": 1, "recipient": "+14*******23", "event": "delivery_sent", ...}
```
(The first line is the HTTP response; the other two are log lines, shortened here.)

> ⚠️ **Trap — compare the two log lines.** `console_message` prints the **full number and the OTP** — that *is* the console sender's purpose (a developer needs to read the code). `delivery_sent`, written by the real service code, shows only `+14*******23`. The first is allowed to exist only because the console sender cannot start in production (§2.12). Real code never logs a full recipient or a body (rules **X-5**, **O-4**).

## 2.3 Bad input is refused before anything is stored

```bash
curl -s -i -X POST $B/send -H 'content-type: application/json' -d '{"channel":"sms","recipient":"98765","template":"otp"}'
```
```
HTTP/1.1 422 Unprocessable Entity
{"error":{"code":"NOTIFICATIONS_INVALID_RECIPIENT","message":"The recipient is not a valid phone number (E.164) or email address.","details":{"channel":"sms","hint":"use E.164, e.g. +14155550123"},"request_id":"01a1537c-d3c3-717a-a0e6-288dd6a8145c"}}
```
Wrong template variables get the same treatment, and the error says exactly what is wrong:
```bash
curl -s -X POST $B/send -H 'content-type: application/json' \
  -d '{"channel":"email","recipient":"a@example.com","template":"otp","variables":{"code":"1"}}'
```
```json
{"error":{"code":"NOTIFICATIONS_TEMPLATE_VARIABLES","message":"The template variables do not match what the template needs.","details":{"template":"otp","missing":["ttl_minutes"],"unexpected":[]},"request_id":"01a1537c-d3d3-769c-821b-bb8b0e9acc35"}}
```
This is the platform's uniform error body (rule **X-3**): a stable `code`, a human `message`, `details`, and the `request_id` to search logs with.

## 2.4 What is *not* exposed

```bash
curl -s -o /dev/null -w 'internal send, no token -> %{http_code}\n' -X POST localhost:18000/internal/v1/notifications/send -H 'content-type: application/json' -d '{}'
curl -s localhost:18000/openapi.json | python3 -c "import sys,json; print([p for p in json.load(sys.stdin)['paths'] if 'notif' in p])"
```
```
internal send, no token -> 401
['/api/v1/notifications/dev/send', '/api/v1/notifications/dev/messages']
```
The real endpoint (`/internal/v1/notifications/send`) needs a **service** token (rule **X-9**) and is hidden from the public schema; only the two dev routes show up — and only because the dev flag is on.

## 2.5 Failover: take the primary provider down

```bash
docker compose stop mailpit
curl -s -X POST $B/send -H 'content-type: application/json' \
  -d '{"channel":"email","recipient":"failover@example.com","template":"welcome","variables":{"name":"Asha"}}'
docker compose logs --no-color app | grep -E 'provider_failover|console_message' | tail -2
docker compose start mailpit
```
```json
{"delivery_id":"01a1537d-0d68-7659-83bb-2e5922606878","status":"sent","provider":"console","attempts":2}
```
```
{"channel": "email", "provider": "smtp", "outcome": "unavailable", "event": "provider_failover", ...}
{"channel": "email", "to": "failover@example.com", "subject": "Welcome, Asha!", "message_body": "Hi Asha, your account is ready.", "event": "console_message", ...}
```
The caller got a normal success; the only visible signs are `provider: console`, `attempts: 2`, the `provider_failover` log line and the metric in §2.10. **The caller never needed to know a vendor was down.** That is the gateway earning its keep.

## 2.6 Idempotency: the same key sends once

```bash
for i in 1 2; do curl -s -X POST $B/send -H 'content-type: application/json' \
  -d '{"channel":"email","recipient":"idem@example.com","idempotency_key":"signup-42"}'; echo; done
curl -s "localhost:8025/api/v1/search?query=to:idem@example.com" | python3 -c "import sys,json; print(json.load(sys.stdin)['messages_count'])"
```
```
{"delivery_id":"01a1537d-1354-768f-a646-7806bc5485eb","status":"sent","provider":"smtp","attempts":1}
{"delivery_id":"01a1537d-1354-768f-a646-7806bc5485eb","status":"sent","provider":"smtp","attempts":1}
1
```
Same `delivery_id` twice, **one** mail in the inbox. Reusing the key for a *different* message is a conflict, not a silent overwrite:
```bash
curl -s -i -X POST $B/send -H 'content-type: application/json' \
  -d '{"channel":"email","recipient":"someone-else@example.com","idempotency_key":"signup-42"}'
```
```
HTTP/1.1 409 Conflict
{"error":{"code":"NOTIFICATIONS_IDEMPOTENCY_CONFLICT","message":"This idempotency key was already used for a different message, or is still in flight.","details":{},"request_id":"01a1537d-13ae-720e-bb09-2b775a6e6de4"}}
```

## 2.7 The rate cap: SMS-pumping defence

The local cap is 50 deliveries per recipient per hour (`NOTIFICATIONS_RATE_LIMIT_PER_HOUR`). Send 52 to the same number:
```bash
for i in $(seq 1 52); do curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/send -H 'content-type: application/json' \
  -d '{"channel":"sms","recipient":"+14155550999","template":"password_changed"}'; done | sort | uniq -c
curl -s -i -X POST $B/send -H 'content-type: application/json' -d '{"channel":"sms","recipient":"+14155550999","template":"password_changed"}' | grep -iE '^HTTP|^retry-after|^\{'
```
```
  50 200
   2 429
HTTP/1.1 429 Too Many Requests
retry-after: 3599
{"error":{"code":"NOTIFICATIONS_RATE_LIMITED","message":"Too many messages were sent to this recipient recently.","details":{},"request_id":"01a1537e-8a6b-7378-a7ab-1cbdaa65196f"}}
```
`Retry-After: 3599` is the number of seconds until the *oldest* counted delivery leaves the one-hour window.

> 💡 **Learning Thought — why this exists.** In "SMS pumping" fraud an attacker repeatedly triggers OTP messages to premium-rate numbers they profit from; **you** pay the bill. A cap per *recipient* (not per caller) is cheap and effective. It's approximate by design (count-then-insert is not atomic): good enough to stop a flood, and the right place for a hard cap later is a Redis counter.

## 2.8 What the database remembers

```bash
docker compose exec -T postgres psql -U postgres -d befastapi -c \
 "select id, channel, recipient_masked, left(recipient_digest,12) as digest, template, status, provider, attempts, error_code, idempotency_key from notifications.deliveries order by created_at limit 6;"
```
```
                  id                  | channel | recipient_masked |    digest    | template | status | provider | attempts | error_code | idempotency_key 
--------------------------------------+---------+------------------+--------------+----------+--------+----------+----------+------------+-----------------
 01a1537c-d127-763c-9253-90d7c4c77274 | email   | a***@example.com | 9040fe33b51b | otp      | sent   | smtp     |        1 |            | 
 01a1537c-d1e2-753b-b48b-803204cfd7f1 | sms     | +14*******23     | 42dc50a42263 | otp      | sent   | console  |        1 |            | 
 01a1537d-0d68-7659-83bb-2e5922606878 | email   | f***@example.com | 3e84e6afdb93 | welcome  | sent   | console  |        2 |            | 
 01a1537d-1354-768f-a646-7806bc5485eb | email   | i***@example.com | 420c0f142d9e | otp      | sent   | smtp     |        1 |            | signup-42
 01a1537e-8442-70d5-a645-a1e14ff03bc6 | sms     | +14*******11     | 1269f0d61768 | otp      | sent   | console  |        1 |            | 
 01a1537e-8477-70f2-94f0-5c0ba9cd3a04 | sms     | +14*******11     | 1269f0d61768 | welcome  | sent   | console  |        1 |            | 
(6 rows)
```
Read it like an auditor: a support engineer can recognise `a***@example.com` and see it went via `smtp` in one attempt; the third row (`attempts = 2`) is the failover from §2.5; the last two rows share a `digest` (same person) without the table containing the number. **No body, no OTP, no full address.**

```bash
docker compose exec -T postgres psql -U postgres -d befastapi -c "select version_num from notifications.alembic_version;"
```
```
 version_num 
-------------
 0002
(1 row)
```

## 2.9 An outage: every provider down

Compose lets you override the provider chain from your shell (the values in `compose.env` are `${VAR:-default}` expressions). Make `static` — a provider that answers `unavailable` — the only email provider:
```bash
NOTIFICATIONS_EMAIL_PROVIDERS=static NOTIFICATIONS_STATIC_OUTCOME=unavailable docker compose up -d --wait app
curl -s -i -X POST $B/send -H 'content-type: application/json' -d '{"channel":"email","recipient":"down1@example.com"}'
```
```
HTTP/1.1 503 Service Unavailable
{"error":{"code":"NOTIFICATIONS_ALL_PROVIDERS_FAILED","message":"No provider could deliver the message.","details":{"delivery_id":"01a1537f-2aec-74b1-92ff-861e59fe0af9","attempts":1},"request_id":"01a1537f-2a8f-757f-9d97-ca774e123fdd"}}
```
The caller gets a `503` that **includes the delivery id** (so a retry or a support ticket can name it). The service logged `delivery_failed` with the recipient *masked*, and wrote a business event in the same transaction as the status change:
```bash
docker compose exec -T postgres psql -U postgres -d befastapi -c \
  "select event_name, attempts, published_at is not null as published, payload from notifications.outbox order by created_at desc limit 1;"
```
```
            event_name            | attempts | published |                                                                                                                                   payload
----------------------------------+----------+-----------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 notifications.delivery_failed.v1 |        0 | t         | {"channel": "email", "event_id": "01a1537f-2b47-7011-bf61-314e11fabd99", "template": "otp", "error_code": "NOTIFICATIONS_ALL_PROVIDERS_FAILED", "delivery_id": "01a1537f-2b44-7410-9341-aea3b5c4780f", "occurred_at": "2026-10-19T09:30:05.511726Z", "correlation_id": null}
```
`published = t`: the relay picked the row up and published it (nobody subscribes yet; Auth will). The payload holds ids and a code — **no recipient**.

A *rejection* is different: chain `static,console` with `static` answering `reject`:
```bash
NOTIFICATIONS_EMAIL_PROVIDERS=static,console NOTIFICATIONS_STATIC_OUTCOME=reject docker compose up -d --wait app
curl -s -i -X POST $B/send -H 'content-type: application/json' -d '{"channel":"email","recipient":"nobody@example.com"}'
```
```
HTTP/1.1 422 Unprocessable Entity
{"error":{"code":"NOTIFICATIONS_RECIPIENT_REJECTED","message":"The provider rejected this recipient.","details":{"delivery_id":"01a1537f-74d2-74d9-8090-e9766ee59010","attempts":1},"request_id":"01a1537f-74ae-7762-af69-bdae8ac540c7"}}
```
`422`, not `503`: it is the *caller's* data that's bad, `attempts` is `1` (the chain stopped; `console` never ran), and it is **not** an outage.

## 2.10 The metrics and the SLO

Metrics reach Prometheus about 15 s after they happen (the export interval). Which metrics exist?
```bash
curl -s 'localhost:9090/api/v1/label/__name__/values' | python3 -c "import sys,json; print([n for n in json.load(sys.stdin)['data'] if n.startswith('notifications')])"
```
```
['notifications_delivery_total', 'notifications_provider_attempt_total', 'notifications_provider_duration_seconds_bucket', 'notifications_provider_duration_seconds_count', 'notifications_provider_duration_seconds_sum', 'notifications_rate_limited_total']
```
(Dotted OTel names become underscored Prometheus names; counters gain `_total`, histograms `_seconds_bucket/_count/_sum`.) After some traffic:
```bash
curl -s --data-urlencode 'query=sum by (channel, provider, outcome) (notifications_provider_attempt_total)' localhost:9090/api/v1/query
```
```
{'channel': 'email', 'outcome': 'rejected', 'provider': 'static'} 1
{'channel': 'email', 'outcome': 'sent', 'provider': 'console'} 4
{'channel': 'email', 'outcome': 'sent', 'provider': 'smtp'} 2
{'channel': 'email', 'outcome': 'unavailable', 'provider': 'smtp'} 1
{'channel': 'email', 'outcome': 'unavailable', 'provider': 'static'} 9
{'channel': 'sms', 'outcome': 'sent', 'provider': 'console'} 56
```
(One row per label combination.) `smtp unavailable = 1` is the failover from §2.5 and `console sent` includes its recovery.

The **delivery SLO** ([`slo.yaml`](../../../services/notifications/observability/slo.yaml)) is a *business* objective — the HTTP layer can be perfectly healthy while no message is delivered. It is of kind `counter_ratio`: failed ÷ all deliveries. With 4 failed and 4 sent deliveries in a fresh process:
```bash
curl -s --data-urlencode 'query=sum(rate(notifications_delivery_total{app_service="notifications",outcome=~"failed"}[5m])) / sum(rate(notifications_delivery_total{app_service="notifications"}[5m]))' localhost:9090/api/v1/query
```
```
0.5
```
That is exactly the expression the generated burn-rate alert (`NotificationsDeliveryBudgetBurn`, three windows, all `health: ok` in Prometheus) compares against its threshold; its runbook section is [`notifications-delivery-burn`](../../../services/notifications/observability/runbook.md). A *rejected* delivery is excluded from "bad" on purpose.

## 2.11 One request, three signals

Send one request and note the `x-request-id` the service returns (`curl -i` shows response headers):
```
HTTP/1.1 200 OK
x-request-id: 01a1538a-5fc3-721e-82bb-3c0956637d96     <- from the second request below
```
Ask Loki for every log line of that request, then take the `trace_id` from them to Tempo:
```bash
curl -s -G localhost:3100/loki/api/v1/query_range --data-urlencode 'query={service_name="befastapi-monolith"} |= "01a1538a-5fc3-721e-82bb-3c0956637d96"'
curl -s localhost:3200/api/traces/4eeef463a834b5855163d14f23210bc7
```
```
delivery_sent {'recipient': 'c***@example.com', 'provider': 'smtp', 'trace_id': '4eeef463a834b5855163d14f23210bc7'}
http_request_completed {'trace_id': '4eeef463a834b5855163d14f23210bc7'}
--- Tempo: trace 4eeef463a834b5855163d14f23210bc7
  POST /api/v1/notifications/dev/send
  fastapi.dependencies
  fastapi.endpoint
  notifications.SendNotification
  fastapi.serialization
```
(Loki lines are shown as `event` + selected fields; the trace lists span names in start order.) Both log lines carry the **same `trace_id`** as the trace, and each also has `app.service: notifications` — stamped automatically (rule **O-7**) — so the "Service" dashboard filtered to `notifications` shows this traffic. Follow the loop from [A2 · 03](../phase-a2/03-the-observability-stack-in-practice.md): metric panel → exemplar → trace → log line.

## 2.12 The production guard, for real

The same image, started with development settings under `ENV=production`:
```bash
docker run --rm -e ENV=production -e NOTIFICATIONS_EMAIL_PROVIDERS=console -e NOTIFICATIONS_DEV_ENDPOINTS=true \
  --entrypoint python befastapi/app:dev -c "from notifications_service.settings import NotificationsSettings; NotificationsSettings()"
```
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for NotificationsSettings
  Value error, refusing to start in production: dev-only providers ['console'] are configured; NOTIFICATIONS_DEV_ENDPOINTS is enabled; NOTIFICATIONS_DIGEST_PEPPER is still the development default [type=value_error, ...]
```
and with a sane production config (real provider, a real pepper, no dev switches):
```bash
docker run --rm -e ENV=production -e NOTIFICATIONS_EMAIL_PROVIDERS=smtp -e NOTIFICATIONS_SMS_PROVIDERS=smtp -e NOTIFICATIONS_DIGEST_PEPPER=s3cret \
  --entrypoint python befastapi/app:dev -c "from notifications_service.settings import NotificationsSettings; s=NotificationsSettings(); print('ok', s.env, s.email_providers)"
```
```
ok production ['smtp']
```
(The second one passes settings validation; the SMS chain naming `smtp` would still be refused later by `build_chains` because SMTP cannot deliver SMS — `test_a_provider_must_support_the_channel_it_serves`.)

## 2.13 Put it back

```bash
docker compose up -d --wait app      # drops your NOTIFICATIONS_* overrides: back to smtp,console
make down                            # or: make reset   (also deletes the database volume)
```

## 🧪 Labs
1. **Mailpit down, then up.** Repeat §2.5, then send again after `docker compose start mailpit`. Which provider handles it, and what do the `attempts` say?
2. **Break the SLO on purpose.** Use the §2.9 override, send 6 emails, wait ~40 s, then evaluate the burn-rate ratio query. Compare with the threshold in `deploy/observability/generated/rules/notifications.slo.rules.yml`. Which window would page first and why?
3. **Prove idempotency survives a restart.** Send with key `restart-1`, run `docker compose restart app`, send again with the same key. Same `delivery_id`? Why does this work?
4. **Find the cap's weak spot.** Send 5 requests *in parallel* for a new number with the cap set to `NOTIFICATIONS_RATE_LIMIT_PER_HOUR=3` (`NOTIFICATIONS_RATE_LIMIT_PER_HOUR=3 docker compose up -d --wait app`). Can more than 3 succeed? Explain, and say what you'd change.

<details><summary>Solutions</summary>

1. Mailpit is first in the chain again, so `smtp` handles it: `provider: smtp`, `attempts: 1`. Failover is per message, not sticky — the primary is tried first every time.
2. 6 failures ÷ 6 deliveries = ratio 1.0, far above every threshold (the fastest pair uses `14.4 × (1 − 0.995) = 0.072`). In the generated file the fast pairs are `severity: page` with `for: 2m` / `for: 15m`, the slow one is `severity: ticket` with `for: 1h` — so a total outage pages within minutes, a slow leak only opens a ticket.
3. Yes, the same id: the key lives in a unique index in PostgreSQL, not in the process's memory.
4. Possibly yes: the cap counts rows *then* inserts, in separate statements, so parallel requests can all see "2 so far". It stops floods, not exact counts. A hard guarantee needs an atomic counter (Redis `INCR` with expiry) or a locking read; documented as a known limit in the use case.
</details>

## 🎯 Interview Questions
1. **A caller gets `503` with a `delivery_id`. What do you check first?** *`get_delivery(id)` for `status`/`error_code`, then the `provider_failover` / `delivery_failed` log lines for that request id, then the provider-attempt metric by `provider, outcome` to see which vendor is down.*
2. **Why is the same email delivered at most once when the caller retries with a key — but a failed delivery is retried?** *A `sent` row means a provider accepted the message, so replaying returns it. A `failed` row means nothing was delivered, so the retry deserves a real attempt on the same row (attempts accumulate).*
3. **Why return `422` for a rejected recipient and `503` when all providers are down?** *`422` is the caller's data; `503` is our dependency. They need different handling (fix the input vs retry later) and different alerting (only `failed` counts against the SLO).*
4. **Why is the delivery SLO a counter ratio rather than HTTP availability?** *A 200 from the HTTP layer says nothing about whether any message left the building; the business outcome is in `notifications_delivery_total{outcome}`.*

## ✅ Self-check
- [ ] I sent an email and saw it in Mailpit, and an SMS and saw it in the log.
- [ ] I caused a failover and can point at the three places it shows (response, log, metric).
- [ ] I can explain `422` vs `503` vs `429` vs `409` from this service.
- [ ] I read `notifications.deliveries` and can say what is deliberately missing.

## 📚 Further reading
- Mailpit — documentation: <https://mailpit.axllent.org/docs/>
- Prometheus — *Instrumentation: counters and `rate()`*: <https://prometheus.io/docs/practices/instrumentation/>
- Google SRE workbook — *Alerting on SLOs*: <https://sre.google/workbook/alerting-on-slos/>
- Twilio — *Fraud Guard / SMS pumping* (what the cap defends against): <https://www.twilio.com/docs/glossary/what-is-sms-pumping-fraud>

**Next:** [B · 03 — What the live run taught us →](03-what-the-live-run-taught-us.md)
