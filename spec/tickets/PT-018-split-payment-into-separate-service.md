# PT-018: Refactor payment into a separate service

Status: Implemented in `spacey-payments`; integration with `spacey` not started.
Date: 2026-10-09
Spec: [payments spec](../payments/spec.md)

## Problem

Payment code lives inside the `spacey` monolith (`payment/`), and `purchase/booking.py` reaches into it directly. Payment changes (e.g. PT-013 refunds) therefore ship with, and are coupled to, bookings. Payments should be its own service with its own repository, database schema and release cycle, reached over HTTP.

## Scope

In:
- New repo `spacey-payments`, a Flask service with the payment API: `POST /bookings/<id>/pay`, `GET /health`.
- Layered structure: `src/app.py` (app factory), `config.py`, `db.py`, `logger.py`, `health.py`, `payments/{api,services,repository}.py`, `payments/models/cards.py`.
- Payment migrations copied from `spacey` (`payments` table, `refunded` status) behind a numbered-SQL migration runner.
- Logging at DEBUG/INFO/WARNING/ERROR in the monolith's `payment booking_id=… outcome=…` format; database failures return 500 `payment unavailable`.
- Tests, Dockerfile, compose file, README, AGENTS.md, and the spec/docs under `spec/`.

Out:
- Subscriptions (they will not live in this service).
- Changing `spacey` to call this service.
- Refund endpoint (PT-013 to be redone here).
- CI/CD and deployment config.

## Acceptance criteria

- [x] Service starts with `flask --app 'src.app:create_app'` and `GET /health` reports status and revision.
- [x] `POST /bookings/<id>/pay` behaves as specified: 404 missing, 200 idempotent when already paid, 400 invalid card, 402 forced failure, 500 database failure, 200 on success storing only the last four digits.
- [x] Schema comes from numbered migrations applied once each (`001_init`, `002_create_payments`, `003_add_refunded_status`).
- [x] No card data or database exception text in logs; levels follow the spec.
- [x] Unit/API tests pass against PostgreSQL (8 tests, run 2026-10-09).
- [x] Layout, commands and rules documented in `README.md`, `AGENTS.md` and `spec/`.
- [ ] Docker image built and the container verified (`docker compose up --build`, `/health` on 8001).
- [ ] CI workflow (test, build) restored; deploy config added.

## Follow-ups

1. `spacey`: replace the in-process payment calls with HTTP calls to this service; decide how booking state (`paid`, `amount_cents`) is shared, since this service currently keeps its own trimmed `bookings` table.
2. Auth between `spacey` and `spacey-payments`.
3. Refund on cancellation (PT-013) as a `spacey-payments` endpoint called by `spacey`; write attempts and refunds to the `payments` table.
4. Luhn check, which the monolith has and this service does not yet.
5. Remove `payment/` from `spacey` once the integration is verified.

## Risks

- Two sources of truth for a booking's paid state until follow-up 1 is decided.
- Network failure between Purchase and Payments; see [ADR 0003](../docs/adr/0003-booking-after-failed-payment.md) for the failed or unknown payment rules.
