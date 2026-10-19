# Notifications — observability catalog

Assets in this folder travel with the service when it is extracted (rule O-8).

| File | Purpose |
|---|---|
| `slo.yaml` | SLIs/SLOs; `tools/sync_observability.py` turns it into burn-rate alert rules (availability, latency, **delivery**) |
| `alerts.rules.yaml` | Hand-written cause alerts (generated SLO rules are emitted separately) |
| `dashboards/` | Grafana dashboards (JSON), provisioned as code |
| `runbook.md` | One section per alert; every alert's `runbook_url` points here |

## Metrics (business)
Prometheus names add `_total` to counters and `_seconds_bucket/_count/_sum` to the histogram. Every series is created at 0 on start-up (`prime_metrics`).

| Name | Type | Attributes (closed sets) | Meaning |
|---|---|---|---|
| `notifications.delivery` | counter | `channel` ∈ {sms,email}, `outcome` ∈ {sent,rejected,failed} | final outcome of each delivery. **`failed` is what the delivery SLO counts as bad** |
| `notifications.provider.attempt` | counter | `channel`, `provider` ∈ {console,memory,static,smtp}, `outcome` ∈ {sent,rejected,unavailable,timeout} | one per provider call — failover shows up here |
| `notifications.provider.duration` | histogram (s) | `channel`, `provider` | time spent in one provider call |
| `notifications.rate_limited` | counter | `channel` | sends refused by the hourly per-recipient cap |

RED metrics (`http.server.request.duration`, …) are automatic and carry `app.service=notifications`.

## SLOs (`slo.yaml`)
`availability` and `latency` on `/api/…` routes (the service has none in production, so they are quiet by design), and **`delivery`**: a
`counter_ratio` SLO — `notifications_delivery_total{outcome="failed"}` ÷ all deliveries, objective 99.5 % / 30 d. Runbook anchor `notifications-delivery-burn`.

## Log events (constant `event` names)
`delivery_sent`, `delivery_failed`, `provider_failover`, `provider_crashed`, plus `http_request_completed` / `request_failed` from the platform.
Recipients appear only masked (`a***@example.com`); message bodies and OTPs never. (The dev-only `console_message` event prints both — it cannot start in production.)

## Spans
`notifications.SendNotification` / `notifications.GetDelivery` (use cases), `notifications_contracts.NotificationsApi.send` / `.get_delivery` (contract calls), `events.publish notifications.delivery_failed.v1`.
