# PT-018: Refactor payment into a separate service

Status: Implemented in `spacey-payments`; integration with `spacey` not started.
Date: 2026-10-09
Spec: [payments spec](../payments/spec.md)

## Problem

Payment code lives inside the `spacey` monolith (`payment/`), and `purchase/booking.py` reaches into it directly. Payment changes (e.g. PT-013 refunds) therefore ship with, and are coupled to, bookings. Payments should be its own service with its own repository, database schema and release cycle, reached over HTTP.

## Scope

In:
- New repo `spacey-payments`, a Flask service owning the `payments` ledger. Its only endpoint for now is `GET /health`.
- Layered structure: `src/app.py` (app factory), `config.py`, `db.py`, `logger.py`, `health.py`, `payments/{api,services,repository}.py`, `payments/models/cards.py`.
- Payment migrations copied from `spacey` (`001_create_payments`, `002_add_refunded_status`) behind a numbered-SQL migration runner.
- Shared logger (DEBUG/INFO/WARNING/ERROR) driven by `LOG_LEVEL`; no card data or database exception text in logs.
- Tests, Dockerfile, compose file, README, AGENTS.md, and the spec/docs under `spec/`.

Out:
- Subscriptions (they will not live in this service).
- Paying a booking (`POST /bookings/<id>/pay`) and any bookings table: that is the booking team's endpoint.
- Changing `spacey` to call this service.
- Refund endpoint (PT-013 to be redone here).
- CI/CD and deployment config.

## Acceptance criteria

- [x] Service starts with `flask --app 'src.app:create_app'` and `GET /health` reports status and revision.
- [x] No bookings table or pay endpoint in this service; `payments` is the only table.
- [x] Schema comes from numbered migrations applied once each (`001_create_payments`, `002_add_refunded_status`).
- [x] No card data or database exception text in logs; levels follow the spec.
- [x] Unit/API tests pass against PostgreSQL (run 2026-10-09).
- [x] Layout, commands and rules documented in `README.md`, `AGENTS.md` and `spec/`.
- [ ] Docker image built and the container verified (`docker compose up --build`, `/health` on 8001).
- [ ] CI workflow (test, build) restored; deploy config added.

## Follow-ups

1. `spacey` / booking team: own the pay endpoint and the booking's `paid` state; decide how payment attempts are recorded in this service's `payments` table.
2. Auth between `spacey` and `spacey-payments`, and the HTTP contract between them: see [ADR 0004](../docs/adr/0004-purchase-payments-communication.md) (proposed).
3. Refund on cancellation (PT-013) as a `spacey-payments` endpoint called by `spacey`; endpoints that write attempts and refunds to the `payments` table.
4. Luhn check, which the monolith has and this service does not yet.
5. Remove `payment/` from `spacey` once the integration is verified.

## Risks

- No code writes to `payments` yet, so the ledger is empty until follow-up 1 or 3 lands.
- Network failure between Purchase and Payments; see [ADR 0003](../docs/adr/0003-booking-after-failed-payment.md) for the failed or unknown payment rules.
