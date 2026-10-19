## What & why

<!-- One or two sentences. Link the issue / ADR. -->

## Architecture checklist (docs/architecture/STANDARDS.md §10)

- [ ] No import of another service's internals (only `*_contracts`) — B-1
- [ ] No new cross-service edge, or `ARCHITECTURE.md §5` updated — B-5
- [ ] No cross-schema SQL/FK; tables in this service's schema; migration in this service's Alembic — D-1…D-3
- [ ] State change + event written via the outbox in one transaction — D-5
- [ ] Contract change is additive; contract tests cover in-process **and** HTTP implementations — C-10, T-3
- [ ] Calls to other services go through a port; batched; ≤ 1 hop; failures handled — C-1…C-5
- [ ] Routers thin; logic in use cases; domain/application framework-free — L-2…L-4
- [ ] Identity/org taken from the `Principal`, never from client input — X-2
- [ ] No secrets/PII/OTP in logs, spans or metrics; metric attributes are closed sets — O-4, O-5
- [ ] New/changed behaviour has spans/metrics where a business question exists; runbook updated for new alerts — O-6, O-8
- [ ] Tests run for this service alone (`make test-service`) — B-6
- [ ] Any rule waiver has an ADR with owner + expiry — STANDARDS §9
- [ ] Learning docs updated for this change (`docs/learning/`, glossary/cheat-sheet/troubleshooting) and `make docs-check` is green — STANDARDS §11

## Test evidence

<!-- Commands run / screenshots / trace links -->
