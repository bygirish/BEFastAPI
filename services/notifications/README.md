# Notifications service

Delivers templated messages (SMS, email) through a **vendor-neutral gateway** with provider failover, a delivery log that never stores
message bodies or full recipients, an idempotency key and a per-recipient hourly cap. Auth (Phase C) will call it to deliver OTPs;
Notifications depends on **no** other service.

| | |
|---|---|
| **Owner** | _team / person_ |
| **Owns (source of truth)** | built-in message templates, the delivery log (`notifications.deliveries`), the provider chain per channel |
| **Public contract** | `contracts/` → package `notifications-contracts`: `NotificationsApi.send / get_delivery`, errors, event `notifications.delivery_failed.v1`, `NotificationsHttpClient` |
| **Depends on (contracts)** | none |
| **DB schema** | `notifications` (own Alembic env in `service/migrations/`: `0001` outbox, `0002` deliveries) |
| **Env prefix** | `NOTIFICATIONS_` — see `service/src/notifications_service/settings.py` and `service/compose.env` |
| **Public routes** | none (users never call it). **Dev only:** `POST /api/v1/notifications/dev/send`, `GET …/dev/messages` when `NOTIFICATIONS_DEV_ENDPOINTS=true` |
| **Internal routes** | `POST /internal/v1/notifications/send`, `GET /internal/v1/notifications/deliveries/{id}` (service principals only) |

## How it works (one paragraph)

`SendNotification` normalises the recipient, renders a built-in template (variables must match exactly), checks the idempotency key and the
hourly cap, records a `pending` delivery (tx 1), asks the `NotificationGateway` to walk the channel's provider chain
(`NOTIFICATIONS_EMAIL_PROVIDERS=smtp,console`: *unavailable/timeout ⇒ next provider; rejected ⇒ stop*), then records `sent` or `failed`
(tx 2; a failure also writes `notifications.delivery_failed.v1` to the outbox). Learn it step by step:
[`docs/learning/phase-b`](../../docs/learning/phase-b/01-notifications-concepts-and-design.md).

## Providers

| Name | Kind | Production? |
|---|---|---|
| `smtp` | email over SMTP (stdlib); locally Mailpit at `mailpit:1025` | yes |
| `console` | prints the message in the app log | **no** (rule X-11) |
| `memory` | keeps messages in a list (tests, dev viewer) | **no** |
| `static` | fixed answer `accept`/`reject`/`unavailable` (`NOTIFICATIONS_STATIC_OUTCOME`) | **no** |

Adding a vendor = one adapter file + three registrations: [lab B·04](../../docs/learning/phase-b/04-lab-add-a-vendor-adapter.md).

## Layout

```
services/notifications/
├── contracts/         # notifications-contracts (public)
├── service/           # notifications-service (private implementation)
│   ├── compose.env    # extra container env for the local stack (copied into docker-compose.yml by `make sync`)
│   ├── migrations/    # own Alembic env
│   ├── tests/
│   └── src/notifications_service/
│       ├── domain/            recipients, templates, provider names, Delivery, errors (pure Python)
│       ├── application/       ports, gateway, telemetry, services/send_notification.py
│       ├── infrastructure/    db/ (tables, repository, UoW), providers/ (console, memory, static, smtp, registry)
│       ├── api/               internal/ (service-to-service), dev/ (development only)
│       └── module.py  settings.py  contracts_impl.py  testing.py
├── observability/     # slo.yaml (incl. the delivery SLO), alerts, runbook — travels with the service
└── Dockerfile
```

## Run / test in isolation

```bash
uv run --package notifications-service pytest services/notifications/service
uv run --package notifications-service alembic -c services/notifications/service/migrations/alembic.ini upgrade head
uv run uvicorn --factory notifications_api.main:create_app --port 8000      # standalone run
```

Read `docs/architecture/STANDARDS.md` (especially X-7 vendors behind ports, X-11 dev-only adapters) before changing anything here.
See `observability/README.md` for the metrics, log events and spans this service emits.
