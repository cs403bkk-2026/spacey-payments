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

Migrations: `001_create_payments.sql`, `002_add_refunded_status.sql` (copied from the `spacey` monolith), and `003_unique_idempotency_key.sql` (unique non-null idempotency keys). Never store a full card number or CVC. Existing duplicate non-null keys must be reconciled before applying migration 003; the migration does not delete ledger entries.

## API

### `GET /health`
`200 {status: "ok", revision}`; `503 {status: "error", error: "database unreachable"}` (logged at ERROR).

### `POST /payments/<payment_id>/refund`
Implemented by PT-019. Records a full mock refund; no money is sent to a provider.
Body: optional JSON object with `reason` (default `cancellation`). An absent body
is accepted; malformed JSON, a non-object body, or a reason that is not a
non-empty string returns `400 {error}` without recording a refund.

| Condition | Response |
|-----------|----------|
| Payment does not exist | `404 {error: "payment not found"}` |
| Payment is `failed`, `unknown` or `refunded` | `409 {error: "payment is not refundable"}` |
| Original success payment already has a refund | `200` existing refund, retaining its original reason |
| Otherwise | `201` new refund |
| Database failure | `500 {error: "payment unavailable"}`, logged at ERROR |

The response is `{payment_id, booking_id, amount_cents, currency, status,
card_last4, reason, created_at}`; `created_at` is ISO 8601 with a timezone.
The new row has `status=refunded`, copies the original payment's `booking_id`,
`amount_cents`, `currency` and `card_last4`, and stores
`idempotency_key=refund:<original_payment_id>`. The original row is unchanged.
Concurrent requests return the same refund: one `201`, the others `200`.
Retry using the original success payment ID, not the refund row's ID.
The `refund:` idempotency-key prefix is reserved for refunds.

Logs use `payment booking_id=<id> outcome=<outcome>`: DEBUG `refund_started`,
INFO `refunded` / `already_refunded`, WARNING `not_found` / `not_refundable` /
`invalid_reason`, ERROR `database_error`. If the booking cannot be read,
`booking_id=None`. No reason text or database diagnostics are logged.

Service authentication is a separate follow-up and is **not implemented**.
Do not expose this endpoint publicly until it is authenticated. Purchase-side
cancellation integration and payment creation are also separate follow-ups;
this endpoint currently requires a seeded success payment.

### Proposed: payment endpoints
Not implemented. Agreed in principle by [ADR 0004](../docs/adr/0004-purchase-payments-communication.md); the booking team has yet to confirm the details. These proposed calls will require the `X-Service-Token` header (`401` otherwise); auth is not implemented yet.

#### `POST /payments`
Body: `booking_id`, `amount_cents` (> 0), `card_number`, `expiry` (`MM/YY`), `cvc`, `idempotency_key` (required), optional `force_failure: true` (test hook).

| Condition | Response |
|-----------|----------|
| Invalid body or card | `400 {error}` (messages as in `models/cards.py`); nothing is recorded |
| Same `idempotency_key` seen before, same `booking_id` and `amount_cents` | Same status code and body as the first time (no second collection) |
| Same `idempotency_key`, different `booking_id` or `amount_cents` | `409 {error: "idempotency_key reused"}` |
| Booking already has a `success` payment under a different key | `409 {error: "booking already paid"}` with the existing payment |
| `force_failure` | `402` and the recorded `failed` payment |
| Outcome cannot be determined | `202` and the recorded `unknown` payment |
| Database failure | `500 {error: "payment unavailable"}`, logged at ERROR |
| Otherwise | `201` and the recorded `success` payment |

A payment body is `{payment_id, booking_id, amount_cents, currency, status, card_last4, reason, created_at}`. After recording, Payments notifies Purchase (see below).

#### `GET /payments/<payment_id>`
`200` payment body; `404 {error: "payment not found"}`. Used to resolve `unknown`.

#### `GET /payments?booking_id=<id>`
`200 {payments: [...]}`, oldest first. Used for reconciliation.

### Proposed: notification to Purchase
After each recorded outcome Payments calls `POST {PURCHASE_URL}/bookings/<booking_id>/payment-result` with `{payment_id, status, amount_cents, occurred_at}` and `X-Service-Token`. A `2xx` means Purchase applied it or had already seen it. On a timeout or non-2xx Payments retries with backoff; a failed notification never changes the recorded payment. Purchase owns the endpoint and the booking update.

## Rules to preserve

1. A failed or unknown payment is never recorded as `success` ([ADR 0003](../docs/adr/0003-booking-after-failed-payment.md)).
2. Card data is validated before anything is written; only `card_last4` is persisted; no card data in logs.
3. Parameterised SQL only. Money is integer cents.
4. Log booking ids and fixed outcomes only, in the form `<event> booking_id=<id> outcome=<outcome>`. DEBUG for start events, INFO for success, WARNING for rejections, ERROR for database failures. Never log card data or database exception text. The level comes from `LOG_LEVEL`.

## Open / not built

- The proposed payment creation/lookup endpoints and notification above. Needs agreement from Purchase.
- Purchase cancellation calling the implemented refund endpoint; removal of monolith refund code.
- Config for `PURCHASE_URL` and `SERVICE_TOKEN`.
- Luhn check: the monolith's `payment.services.validate_card` has it; this service does not yet.
