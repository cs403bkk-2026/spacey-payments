# Payments service spec

Service: `spacey-payments`. Status: **as implemented 2026-10-09** (mocked, no real provider). Items under "Open" are not built yet.

## Responsibilities

- Decide whether a card payment for a booking is accepted (mocked).
- Own a booking's paid state and the last four card digits.
- Not responsible for spaces, users, access codes, reservations or subscriptions - those live in other services, so there are no foreign keys into them.

## Data

| Table | Columns |
|-------|---------|
| `bookings` | `id`, `member`, `paid`, `amount_cents` (integer cents), `card_last4` |
| `payments` | `id`, `booking_id` (no FK), `amount_cents` (> 0), `currency` (`USD`), `status` (`success`, `failed`, `unknown`, `refunded`), `reason`, `card_last4`, `idempotency_key`, `created_at`. Schema only: no code writes to it yet. |

Never store a full card number or CVC. Money is always integer cents.

## API

### `GET /health`
`200 {status: "ok", revision}`; `503 {status: "error", error: "database unreachable"}`.

### `POST /bookings/<id>/pay`
Body: `card_number`, `expiry` (`MM/YY`), `cvc`, optional `force_failure: true` (test hook that makes the attempt fail).

| Condition | Response |
|-----------|----------|
| Booking does not exist | `404 {error: "booking not found"}` |
| Booking already paid | `200` booking row (no card needed, nothing charged again) |
| Card invalid | `400 {error}`: `card_number must be 13-19 digits`, `cvc must be 3 or 4 digits`, `expiry must be in MM/YY format`, `card has expired` |
| `force_failure` | `402 {error: "payment failed"}`; booking stays unpaid |
| Database failure | `500 {error: "payment unavailable"}`; logged at ERROR with the booking id only |
| Otherwise | `200` booking row with `paid: true`, `card_last4` set |

Paying is idempotent: retrying a successful payment returns the same paid booking.

## Rules to preserve

1. Idempotent pay.
2. A failed or rejected payment never marks a booking paid ([ADR 0003](../docs/adr/0003-booking-after-failed-payment.md)).
3. Card data is validated before anything is written; only `card_last4` is persisted; no card data in logs.
4. Parameterised SQL only.
5. Log booking ids and fixed outcomes only (`payment booking_id=<id> outcome=<outcome>`): DEBUG `started`; INFO `succeeded`, `already_paid`; WARNING `not_found`, `invalid_card`, `failed`; ERROR `database_error`. Never log card data or database exception text. Level is set by `LOG_LEVEL`.

## Open / not built

- Refund on booking cancellation (started in monolith PR #260; to be redone here, e.g. `POST /bookings/<id>/refund`, called by `spacey` when a paid booking is cancelled). Needs: a refund record, idempotency, and a decision on partial failure between delete and refund.
- Luhn check: the monolith's `payment.services.validate_card` has it; this service does not yet.
- Write payment attempts and refunds to the `payments` table (schema migrated, unused by code).
- Migrations and tests directory.
- Auth between `spacey` and this service.
