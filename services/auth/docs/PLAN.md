# Auth & RBAC Service — Implementation Plan

Status: **DRAFT v2 — decisions Q1–Q8 resolved (see §12)** · Stack: Python 3.12 + FastAPI · Date: 2026-10-18

> Note: an earlier session recorded decisions in `services/auth/Auth_Requirements.md`, but that file is not in
> this repo (only `README.md` is committed). This plan carries those decisions forward where they still fit.
> The one that changed: signup is no longer phone-required (Q1).

> **Architecture update (2026-10-19):** Auth is now one service in an extraction-ready modular monolith. Folder layout (§3),
> the OTP delivery facade (§5), and profile fields (§4) are superseded where they conflict with
> [docs/architecture/ARCHITECTURE.md](../../../docs/architecture/ARCHITECTURE.md) — see its **§14 Reconciliation** for the exact mapping.
> Short version: code lives in `services/auth/src/auth_service/` (layered); OTP *delivery* moves to the Notifications service
> (Auth keeps OTP code ownership and static-OTP mode); profile fields move to the Users service.

**Decisions at a glance:** signup with phone / email / Google · JSON bearer tokens only · **org-scoped RBAC from day one** ·
Google via client `id_token` · auto-link on verified email · Postgres + Redis · standalone service (JWKS) · region-agnostic.

---

## 1. Goals & non-goals

**Goals**
- JWT-based authentication via: Email+Password, Phone+Password, Email+OTP, Phone+OTP, Google SSO.
- OTP delivery behind a **vendor-neutral facade**, with a **static-OTP mode** for dev/test.
- Complete lifecycle flows: signup, login, resend OTP, forgot/reset/change password, account lock/unlock,
  token refresh/logout, session management, identity (email/phone) management.
- RBAC: roles → permissions, enforced by FastAPI dependencies; admin APIs to manage them.
- Other services can verify tokens offline via a **JWKS** endpoint.

- Multi-tenant RBAC: users belong to one or more **organizations**; roles are granted per organization (plus a small set of platform-level roles).

**Non-goals (v1)**: full MFA/TOTP (phase 8), API keys, service-to-service OAuth client-credentials, hosted login UI,
SSO/SAML per organization, server-side Google redirect flow, cookie-based token delivery.

---

## 2. Tech stack

| Concern | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | async, typed schemas |
| DB | PostgreSQL + SQLAlchemy 2.0 (async) + Alembic | relational integrity for users/roles |
| Cache / ephemeral | Redis | OTP challenges, rate limits, lockout counters, token denylist |
| Password hashing | `argon2-cffi` (argon2id) + server-side pepper | current best practice |
| JWT | `PyJWT` + `cryptography` (RS256, `kid`) | asymmetric → JWKS for other services |
| Google SSO | `google-auth` (ID-token verify) | Q4: client sends the ID token |
| Phone parsing | `phonenumbers` (E.164 normalisation) | prevents duplicate identities |
| Email validation | `email-validator` | |
| Config | `pydantic-settings` | env-driven, per-environment |
| Tooling | `uv`, `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `httpx`, `testcontainers` | |
| Local infra | `docker-compose` (Postgres + Redis) | |

---

## 3. Architecture

Layered, dependency-injected; routers stay thin.

```
services/auth/
├── app/
│   ├── main.py                     # app factory, middleware, router mounting
│   ├── core/                       # config, security (hash/jwt), errors, logging, clock, ids
│   ├── db/                         # engine, session, base
│   ├── models/                     # SQLAlchemy models
│   ├── schemas/                    # Pydantic request/response models
│   ├── repositories/               # DB access only (no business rules)
│   ├── services/                   # business logic
│   │   ├── auth_service.py         # signup/login orchestration
│   │   ├── otp_service.py          # OWNS code gen/hash/verify/resend/attempts
│   │   ├── password_service.py
│   │   ├── token_service.py        # access/refresh/signup tokens, rotation, JWKS
│   │   ├── lockout_service.py
│   │   ├── sso_service.py
│   │   ├── rbac_service.py
│   │   ├── org_service.py          # orgs, memberships, invitations
│   │   ├── session_service.py
│   │   └── audit_service.py
│   ├── providers/
│   │   ├── notify/                 # ← OTP delivery FACADE (see §5)
│   │   └── sso/                    # google.py (+ base for future IdPs)
│   ├── api/v1/                     # auth, otp, password, sso, sessions, me, admin_rbac, admin_users
│   └── deps/                       # current_user, require_permission, rate_limit, client_info
├── alembic/
├── tests/{unit,integration,contract,security}/
└── docs/PLAN.md
```

**Principle:** `OtpService` owns the *code* (generate, hash, expire, attempt-count, single-use). The facade only
*delivers a message*. Because we own verification, swapping vendors never changes OTP semantics. (Avoid
vendor-managed "verify" products such as Twilio Verify — they'd leak vendor semantics into the core.)

---

## 4. Data model

Identity is split from user so one user can hold several login identifiers (phone, email, Google).

```
users
  id (uuid pk), status [pending|active|locked|suspended|disabled|deleted],
  display_name, avatar_url, locale, timezone,
  password_hash NULL, password_updated_at NULL, must_change_password,
  failed_login_count, last_failed_at, locked_until NULL, lock_reason NULL, locked_by NULL,
  token_version int,            -- bump to invalidate all access tokens
  last_login_at, created_at, updated_at, deleted_at NULL

user_identities
  id, user_id fk, type [phone|email|google],
  value_normalized (E.164 / lower-cased email / google `sub`),
  is_primary, verified_at NULL, created_at
  UNIQUE (type, value_normalized)       -- one account per identifier

otp_challenges   (Redis primary; DB mirror only if audit needs it)
  id, identity_type, identity_value, purpose [signup|login|verify_identity|password_reset|step_up|unlock],
  code_hmac, attempts, max_attempts, resend_count, last_sent_at, expires_at, consumed_at, ip, device_id

refresh_tokens
  id, user_id, session_id, family_id, token_hash, parent_id NULL,
  issued_at, expires_at, rotated_at NULL, revoked_at NULL, revoked_reason, replaced_by NULL

sessions                       -- one per device login; refresh tokens chain under it
  id, user_id, device_label, user_agent, ip, created_at, last_seen_at, revoked_at

organizations
  id, name, slug UNIQUE, status [active|suspended|deleted], created_by, created_at, deleted_at NULL

org_memberships              -- who belongs to which org
  id, org_id fk, user_id fk, status [active|invited|removed], joined_at, invited_by
  UNIQUE (org_id, user_id)

org_invitations
  id, org_id, identity_type, identity_value, role_id, token_hash, invited_by, expires_at, accepted_at NULL, revoked_at NULL

permissions      id, code UNIQUE  (e.g. "members:invite"), description, level [platform|org]
roles            id, org_id NULL, name, description, is_system, level [platform|org]
                 -- org_id NULL + is_system = built-in template (e.g. org_owner, org_admin, org_member)
                 -- org_id set = custom role defined by that org
                 UNIQUE (org_id, name)
role_permissions (role_id, permission_id)
role_assignments (id, user_id, role_id, org_id NULL, granted_by, granted_at, revoked_at NULL)
                 -- org_id NULL = platform-level grant (super_admin, support); otherwise the grant applies only in that org.
                 -- invariant: the user must have an active org_membership for org_id

audit_log        id, ts, actor_user_id, subject_user_id, event, outcome, ip, user_agent, request_id, metadata jsonb
```

Seed (migration): permissions; platform roles `super_admin`, `support`; org role templates `org_owner`, `org_admin`,
`org_member`; and a bootstrap super-admin via env.

---

## 5. OTP delivery facade (vendor-neutral)

```python
class Channel(StrEnum): SMS="sms"; EMAIL="email"; WHATSAPP="whatsapp"   # extensible

@dataclass(frozen=True)
class OtpMessage:
    channel: Channel
    recipient: str          # E.164 or email
    code: str
    purpose: OtpPurpose
    ttl_seconds: int
    locale: str = "en"
    request_id: str = ""

@dataclass(frozen=True)
class DeliveryResult:
    accepted: bool
    provider: str
    provider_message_id: str | None = None
    error_code: str | None = None       # normalised, vendor-agnostic

class OtpSender(Protocol):               # what a vendor adapter implements
    name: str
    channels: frozenset[Channel]
    async def send(self, msg: OtpMessage) -> DeliveryResult: ...

class NotificationGateway:               # what the rest of the app talks to (the Facade)
    def __init__(self, routes: dict[Channel, list[OtpSender]], templates: TemplateRenderer): ...
    async def send_otp(self, msg: OtpMessage) -> DeliveryResult   # tries providers in order (failover)
```

**Providers shipped in v1**
- `StaticOtpSender` — *does not call anything*; the fixed code is injected at generation time (see below).
- `ConsoleSender` — logs the message (dev).
- `InMemorySender` — captures messages in a list for tests (`gateway.outbox`).
- Adapters for the real vendors (Twilio / MSG91 / SES / SendGrid …) are added later by implementing `OtpSender`
  and registering in config — **no change to services or routes**.

**Wiring:** `NOTIFY_SMS_PROVIDERS=twilio,msg91` / `NOTIFY_EMAIL_PROVIDERS=ses` (ordered = failover chain).
Vendor templates/DLT ids (India SMS) live in adapter config, not in core.

**Static OTP mode**
- `OTP_MODE=static` → `OtpService` uses `OTP_STATIC_CODE` (default `123456`) instead of a random code; hashing,
  expiry, attempts and single-use still apply, so tests exercise the real code path.
- Optional `OTP_STATIC_ALLOWLIST` (regex/list of test numbers/emails): static code applies *only* to those
  recipients; everyone else gets a random code. Lets staging be tested with real users alongside test accounts.
- **Safety:** app **refuses to boot** if `ENV=production` and `OTP_MODE=static`; startup logs a loud warning in other envs.
- Delivery still goes through the gateway (Console/InMemory), so the flow is identical to production.

Delivery is dispatched after the response path via an outbox/background task so vendor latency doesn't leak
account existence through timing.

---

## 6. Flows & endpoints (`/api/v1`)

Responses to *request-OTP* and *forgot-password* are **always generic** (no account enumeration).

### 6.1 Signup (two-step; `identifier` may be a phone **or** an email — Q1)
| Endpoint | Purpose |
|---|---|
| `POST /auth/signup/otp/request` `{identifier}` | send OTP (purpose=signup) → `challenge_id` |
| `POST /auth/signup/otp/verify` `{challenge_id, code}` | → short-lived **signup token** (`scope: signup_complete`, 10 min) |
| `POST /auth/signup/complete` (Bearer signup token) `{name, password?, terms_version}` | create user + **personal org** (user = `org_owner`, Q9) → full tokens with that org active |

Google signup uses `POST /auth/sso/google` (§6.2): an unknown, verified Google identity creates the account directly.
Every account must hold ≥1 verified identifier; the other identifier type is added later via §6.7.

### 6.2 Login (4 methods + SSO)
| Endpoint | Method |
|---|---|
| `POST /auth/login/password` `{identifier, password}` | Email+Password / Phone+Password (identifier type auto-detected) |
| `POST /auth/login/otp/request` `{identifier}` → `POST /auth/login/otp/verify` `{challenge_id, code}` | Email+OTP / Phone+OTP |
| `POST /auth/sso/google` `{id_token}` | Google SSO (client obtains the ID token; no server redirect flow — Q4) |

All success paths return `{access_token, refresh_token, expires_in, token_type}` and create a `session`.
`amr` claim records how the user authenticated (`pwd`, `otp_sms`, `otp_email`, `google`).

### 6.3 OTP resend
`POST /auth/otp/resend {challenge_id}` — rules:
- Cooldown between sends (default 30 s), max **3 resends** per challenge, max **5 challenges/hour** per identifier,
  per-IP and per-device caps. Excess → `429` + `Retry-After`.
- Resend **invalidates the previous code** and resets `expires_at`; `attempts` carry over (so resend can't reset brute-force budget).
- Verify: max **5 attempts** per challenge, constant-time compare of HMAC, single-use, 5-min TTL.

### 6.4 Forgot / reset / change password
| Endpoint | Notes |
|---|---|
| `POST /auth/password/forgot {identifier}` | generic response; sends OTP (purpose=password_reset) to the identifier |
| `POST /auth/password/reset/verify {challenge_id, code}` | → single-use **reset token** (5 min) |
| `POST /auth/password/reset {reset_token, new_password}` | sets password, **revokes all sessions**, bumps `token_version`, notifies user, clears lockout |
| `POST /auth/password/change {current_password, new_password}` | authenticated; revokes other sessions |
| `POST /auth/password/set {new_password}` | for OTP/Google-only users; requires recent auth (≤5 min) or step-up OTP |

Password policy (NIST 800-63B style): min 10 chars, max 128, no composition rules, reject common/breached
passwords (local list; HIBP k-anonymity optional), reject equal to identifier.

### 6.5 Account lock / unlock
**Automatic lock** (`lockout_service`)
- Counter per account across *all* credential checks (password + OTP verify), plus a separate per-IP throttle.
- Progressive: 5 failures → locked 15 min; repeat within 24 h → 1 h → 24 h. Success resets counter.
- Locked login returns a generic `ACCOUNT_LOCKED` with `retry_after` (revealed only after credential/OTP step so an
  attacker can't probe lock state for arbitrary accounts).

**Unlock paths**
1. Auto-expiry (`locked_until`).
2. **Self-unlock**: `POST /auth/account/unlock/request` → OTP to a verified identity → `…/unlock/verify` (also forces password reset if the lock reason was brute-force).
3. **Admin**: `POST /admin/users/{id}/lock {reason}` / `…/unlock` — permission `users:lock`; admin lock revokes all sessions immediately and does not auto-expire.

Statuses: `pending → active ⇄ locked`, plus `suspended` (admin/fraud, no self-unlock), `disabled`, `deleted`.
DoS-by-lockout mitigations: lock is temporary, self-unlock exists, and failure counting is keyed on (account, ip) in
addition to the global account counter before escalating.

### 6.6 Tokens & sessions
| Endpoint | Notes |
|---|---|
| `POST /auth/token/refresh` | opaque refresh token, **rotation + reuse detection** (reuse of a rotated token revokes the whole family/session) |
| `POST /auth/token/switch-org` `{org_id}` | re-issue an access token whose active org is `org_id` (membership checked) |
| `POST /auth/logout` | revoke current session |
| `POST /auth/logout-all` | revoke all sessions + bump `token_version` |
| `GET /me/sessions`, `DELETE /me/sessions/{id}` | device/session management |
| `GET /.well-known/jwks.json` | public keys for other services |

### 6.7 Identity management (authenticated)
- `GET /me`, `PATCH /me`
- `POST /me/identities/email|phone` → OTP verify to **add/verify** an identifier (add the second identifier type after signup)
- `PUT /me/identities/phone` change phone: OTP to *new* number + step-up on old credential
- `DELETE /me/identities/{id}`: blocked if it would leave the user with no login method
- `POST /me/sso/google/link`, `DELETE /me/sso/google` (unlink; same last-method guard)

### 6.8 Other flows I recommend (beyond your list)
| Flow | Phase | Reason |
|---|---|---|
| Refresh rotation + reuse detection | 1 | stolen-token containment |
| Session/device list & remote logout | 6 | basic account hygiene |
| Audit log (+ admin query API) | 1/6 | forensics, compliance |
| New-device / password-changed / lock notifications | 6 | user-visible tamper detection |
| Step-up auth (recent-auth check) for sensitive ops | 3 | change phone, set password, delete account |
| Account deletion (soft-delete, 30-day grace, then anonymise) | 6 | privacy-law readiness |
| Abuse controls on OTP send (captcha hook, per-country allowlist, SMS-pumping detection) | 2 | SMS cost fraud is the #1 OTP abuse |
| TOTP MFA + recovery codes | 7 | optional hardening |
| Email magic-link login (reuses OTP infra) | 7 | optional |
| Terms/consent version acceptance at signup | 1 | commonly required |

---

## 7. JWT design

- **Access token** (15 min, RS256, header `kid`): `iss, aud, sub, iat, exp, jti, sid, ver (token_version), amr,
  org (active org id | null), roles[] (role names in the active org), plat_roles[] (platform roles)`.
  Permissions are **not** embedded (keeps tokens small, avoids staleness) — resolved from roles server-side.
  Users in several orgs hold one active org at a time and switch with `/auth/token/switch-org`.
- **Refresh token**: opaque 256-bit random, stored **hashed**, 30 days, rotating, family tracked.
- **Signup / reset / unlock tokens**: scoped JWTs (`scope` claim), 5–10 min, single-use (jti stored in Redis), accepted *only* by their target endpoint.
- **Key management:** private key from env/secret manager; support ≥2 active keys (`kid`) for rotation; JWKS publishes all.
- **Validation dependency** checks signature, `iss/aud/exp`, `scope == access`, session not revoked, `ver` matches (cached in Redis, 1 lookup).
- Delivery: JSON bearer only (Q2); clients keep tokens in memory / secure storage. No cookie or CSRF machinery in v1.

---

## 8. RBAC design

- **Two levels** (Q3 — org-scoped from day one):
  - **Platform level** (`org_id NULL`): `super_admin`, `support`. Manage users and orgs across the system (lock/unlock users, suspend orgs).
  - **Org level**: built-in templates `org_owner`, `org_admin`, `org_member` (custom roles per org deferred).
    A grant applies only inside its org. Custom roles are a later addition (Q12).
- **Model:** `user —< role_assignments(org_id) >— role —< role_permissions >— permission`, gated by `org_memberships`.
  Permissions are `resource:action` strings with a `level`: platform (`users:lock`, `orgs:suspend`) or org
  (`members:invite`, `roles:manage`, `org:update`). Seeded by migration; code declares required permissions.
- **Enforcement:** `Depends(require_permission("members:invite"))` evaluates against the token's **active org** (`org` claim);
  an org-level permission never passes for a different org, and platform permissions need a platform role.
  `require_platform_permission("users:lock")` for platform routes. Routes with `{org_id}` in the path must match the token's `org`
  (or the caller needs a platform role).
- **Caching:** role→permission map cached in-process (TTL 60 s) with Redis pub/sub invalidation. Membership/role changes
  take effect on next token refresh (≤15 min); sensitive permissions (`roles:manage`, `members:remove`) also check the DB live.
  Removing a member revokes that user's sessions' active-org if it equals the org (forces re-issue).
- **Org lifecycle APIs:** `POST /orgs`, `GET /orgs`, `PATCH /orgs/{id}`, `DELETE /orgs/{id}` (owner only, soft delete);
  members: `GET/DELETE /orgs/{id}/members`, `PATCH …/members/{uid}/role`, `POST …/leave`, `POST …/transfer-ownership`;
  invitations: `POST /orgs/{id}/invitations` (invite by email or phone, delivered through the notification gateway),
  `POST /invitations/accept` (existing user, authenticated), `DELETE …/invitations/{id}`.
  **Invite for an unknown identifier (Q11):** the invite token is a scoped JWT carrying `org_id`, `role`, and the invited identifier.
  The invitee verifies that identifier by OTP, completes signup, and is auto-joined with the invited role. In this path the
  personal org is still created, but the invited org becomes the active org on first login. Invites expire in 7 days, are single-use,
  and cannot grant `org_owner`.
- **Role APIs (v1, built-in roles only — Q12):** `GET /orgs/{id}/roles`, `GET /permissions` (catalog), and member role changes via
  `PATCH /orgs/{id}/members/{uid}/role`. Custom-role CRUD (`POST/PATCH/DELETE /orgs/{id}/roles`, `PUT …/permissions`) is **deferred**; the
  schema and escalation guards are already built for it. **Platform admin APIs** under `/admin/...`: platform grants, org suspend, user lock.
- **Guards:** built-in role templates immutable; every org keeps ≥1 `org_owner`; can't grant or edit a role with permissions
  you don't hold (no privilege escalation); custom roles cannot hold platform permissions; every change audited.

---

## 9. Security & cross-cutting

- **No enumeration**: identical responses/timing for known vs unknown identifiers (dummy hash verify, async delivery).
- **Rate limiting** (Redis sliding window): per IP, per identifier, per endpoint class; `429` + `Retry-After`.
- **Secrets** hashed at rest: passwords (argon2id+pepper), OTP (HMAC-SHA256 with server key), refresh tokens (SHA-256).
- **Google SSO:** verify ID token signature, `aud`, `iss`, `exp`, `email_verified`; key identity on `sub`, not email.
  Linking to an existing account only when Google email is verified **and** matches a *verified* local email (Q5).
- **Hardening:** CORS allowlist, security headers, request-ID middleware, structured JSON logs with PII masking
  (never log codes/passwords/tokens), uniform error model `{error:{code,message,details,request_id}}`.
- **Config safety:** boot fails on insecure combos (static OTP in prod, missing keys, debug in prod).
- **Clock injection** for deterministic expiry tests.

---

## 10. Phased delivery

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 Scaffold** | uv project, app factory, config, docker-compose (PG+Redis), Alembic, lint/type/test CI, health, error model, logging, request-ID | `pytest` + `ruff` + `mypy` green in CI; `/healthz` up |
| **1 Core auth** | schema + seed, password hashing, token service (JWT/JWKS/refresh rotation), signup (password), login/password, refresh, logout, `/me`, audit | register→login→refresh→logout works; reuse-detection test passes |
| **2 OTP + facade** | `NotificationGateway`, Static/Console/InMemory senders, `OtpService`, signup/login OTP, resend, rate limits | all four login methods work end-to-end with static OTP; contract-test suite for any `OtpSender` |
| **3 Password lifecycle + lockout** | forgot/reset/change/set, step-up, auto-lock + progressive backoff, self-unlock | brute-force test locks account; reset clears lock & revokes sessions |
| **4a Orgs & memberships** | org CRUD, memberships, invitations (via gateway), `switch-org`, `org` claim in tokens | personal org on signup; create org → invite (existing and unknown invitee) → accept → switch-org flow green; cross-org isolation tests |
| **4b RBAC** | permission catalog + seeds, built-in org roles + platform roles, `require_permission` / `require_platform_permission`, caching | permission matrix tests; last-owner and no-escalation guards |
| **5 Google SSO** | ID-token verify, create/link/unlink, `amr`, edge cases (unverified email, existing account) | mocked-Google integration tests green; manual test with real client ID |
| **6 Sessions, admin & hardening** | session list/revoke, admin lock/unlock/suspend (user + org), notifications, account deletion, security review | OWASP ASVS L2 checklist pass; load-test OTP/login |
| **8 Optional** | TOTP MFA, magic link, real vendor adapter(s), per-org SSO | per need |

Each phase merges as its own PR with tests; Phases 1–3 deliver a usable authentication service, 4a/4b add multi-tenant authorization.
Phase 4 is the largest change from v1 of this plan (org scope from day one).

---

## 11. Testing strategy

- **Unit**: services with fakes (clock, in-memory Redis/repo, `InMemorySender`).
- **Integration**: real Postgres + Redis via testcontainers; full HTTP flows through `httpx.AsyncClient`.
- **Contract**: one parametrised suite every `OtpSender` implementation must pass (accepts valid msg, normalised errors, no code leakage in logs).
- **Security**: replayed OTP, expired OTP, attempt exhaustion, resend not resetting attempts, refresh reuse, token with wrong `scope`/`aud`/`kid`, enumeration timing/shape, lockout escalation and unlock, cross-org isolation, last-org-owner guard, privilege-escalation guard, static-OTP-in-prod boot refusal.
- **Targets**: ≥90 % line coverage on `services/`, 100 % on token + OTP + lockout modules.

---

## 12. Decisions

### Resolved
| # | Topic | Decision |
|---|---|---|
| Q1 | Signup identifier | Phone **or** email **or** Google; every account needs ≥1 verified identifier |
| Q2 | Token delivery | JSON bearer only (no cookies/CSRF in v1) |
| Q3 | Tenancy | **Org-scoped RBAC from day one**, plus platform-level roles |
| Q4 | Google flow | Client sends `id_token`; backend verifies |
| Q5 | Account linking | Auto-link when Google email is verified and matches a *verified* local email |
| Q6 | Infra | Postgres + Redis |
| Q7 | Topology | Standalone service; other services verify via JWKS |
| Q8 | Region | Region-agnostic; region specifics live in vendor adapters/config |
| Q9 | Org on signup | Auto-create a **personal org** for every new user (user becomes `org_owner`); it becomes their default active org |
| Q10 | Multiple orgs | A user may belong to many orgs; one active org per token, changed via `switch-org` |
| Q11 | Invitations | Invite link works for unknown invitees: verify invited identifier → signup → auto-join the org with the invited role |
| Q12 | Custom roles | **Built-in org roles only in v1** (`org_owner`, `org_admin`, `org_member`); schema keeps `roles.org_id` so custom-role APIs can follow later |

### Still open
None blocking. Revisit when the first real consumer service integrates (e.g. whether downstream services want permissions in the token).
