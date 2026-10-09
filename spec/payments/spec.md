# Payments service spec

Service: `spacey-payments`. Status: **as implemented 2026-10-09**. No payment provider is integrated. Items under "Open" are not built yet.

## Responsibilities

- Own the `payments` ledger: payment attempts and refunds, keyed by `booking_id`.
- Validate card details (shape and expiry only) in `payments/models/cards.py`.
- Not responsible for bookings, spaces, users, access codes or subscriptions. Paying a booking (`POST /bookings/<id>/pay`) is the booking team's endpoint, so this service has no foreign keys into those domains and never touches a bookings table.

## Data

| Table | Columns |
|-------|---------|
| `payments` | `id`, `booking_id` (no FK), `amount_cents` (> 0, integer cents), `currency` (`USD`), `status` (`success`, `failed`, `unknown`, `refunded`), `reason`, `card_last4`, `idempotency_key`, `created_at` |

Migrations: `001_create_payments.sql`, `002_add_refunded_status.sql` (copied from the `spacey` monolith). Never store a full card number or CVC.

## API

### `GET /health`
`200 {status: "ok", revision}`; `503 {status: "error", error: "database unreachable"}` (logged at ERROR).

No other endpoints yet.

## Rules to preserve

1. A failed or unknown payment is never recorded as `success` ([ADR 0003](../docs/adr/0003-booking-after-failed-payment.md)).
2. Card data is validated before anything is written; only `card_last4` is persisted; no card data in logs.
3. Parameterised SQL only. Money is integer cents.
4. Log booking ids and fixed outcomes only, in the form `<event> booking_id=<id> outcome=<outcome>`. DEBUG for start events, INFO for success, WARNING for rejections, ERROR for database failures. Never log card data or database exception text. The level comes from `LOG_LEVEL`.

## Open / not built

- Endpoints over the `payments` table: record a payment attempt, and refund on booking cancellation (started in monolith PR #260, to be redone here). Needs idempotency and a decision on partial failure between cancel and refund.
- Luhn check: the monolith's `payment.services.validate_card` has it; this service does not yet.
- Auth between `spacey` and this service.
