# Notifications runbook

One `##` section per alert. The section id is used as the alert's `runbook_url` anchor.

## notifications-availability-burn
**Symptom:** error budget for availability is burning fast.
**First checks:** Grafana → "Service" dashboard (`app_service=notifications`) → error ratio panel → exemplar → trace → logs.
**Mitigation:** the service has no public routes, so 5xx here means *internal* callers are failing: check which service's contract call
span fails (`notifications_contracts.NotificationsApi`) and whether the database is reachable (`/readyz`).

## notifications-latency-burn
**Symptom:** too many slow requests on public routes (threshold in `slo.yaml`).
**First checks:** Grafana → "RED overview" → latency p95 panel → click an exemplar dot → trace → find the slow span (database? a provider?).
**Mitigation:** a slow or hanging provider is bounded by `NOTIFICATIONS_ATTEMPT_TIMEOUT_SECONDS`; if one provider is consistently slow, move it behind a faster one in the chain.

## notifications-delivery-burn
**Symptom:** messages are failing to reach *any* provider: `notifications_delivery_total{outcome="failed"}` is a large share of all deliveries.
**First checks:**
1. Grafana → Explore → Prometheus: `sum by (provider, outcome) (rate(notifications_provider_attempt_total[5m]))` — which provider is `unavailable`/`timeout`?
2. Loki: `{service_name=~".+"} |= "provider_failover"` shows each failover; `|= "delivery_failed"` shows the end of the chain (recipients are masked).
3. Is the cause on our side (network, credentials, the SMTP relay) or the vendor's status page?
**Mitigation:** put a healthy provider first in the chain (`NOTIFICATIONS_EMAIL_PROVIDERS` / `NOTIFICATIONS_SMS_PROVIDERS`, comma separated, then restart). Never "fix" this by adding `console`/`static`/`memory` — they refuse to start in production on purpose (rule X-11).
**Follow-up:** subscribers of `notifications.delivery_failed.v1` (e.g. Auth) can offer the user another channel.
