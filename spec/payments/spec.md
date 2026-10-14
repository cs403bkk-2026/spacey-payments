# Payments service spec

Service: `spacey-payments`. Status: **as implemented 2026-10-12**. No payment provider is integrated. Items under "Open" are not built yet. The machine-readable contract is [`openapi.yaml`](../../openapi.yaml).

## Responsibilities

- Own the `payments` ledger: payment attempts and refunds, keyed by `booking_id`.
- Validate card details (ASCII digit shape, Luhn checksum and expiry) in `src/domain/card.py`.
- Not responsible for bookings, spaces, users, access codes or subscriptions. Paying a booking (`POST /bookings/<id>/pay`) is the booking team's endpoint, so this service has no foreign keys into those domains and never touches a bookings table.

## Data

| Table | Columns |
|-------|---------|
| `payments` | `id`, `booking_id` (no FK), `amount_cents` (> 0, integer cents), `currency` (`USD`), `status` (`success`, `failed`, `unknown`, `refunded`), `reason`, `card_last4`, `idempotency_key`, `created_at` |

Migrations: `001_create_payments.sql`, `002_add_refunded_status.sql` (copied from the `spacey` monolith), `003_add_payment_unique_indexes.sql` (one row per `idempotency_key`; at most one `success` per `booking_id`). Applied once each at startup and tracked in `schema_migrations`. Never store a full card number or CVC.

## API

### `GET /health`
`200 {status: "ok", revision}`; `503 {status: "error", error: "database unreachable"}` (logged at ERROR).

### Authentication
Every endpoint except `/health` requires `X-Service-Token` equal to `SERVICE_TOKEN`; otherwise `401 {error: "unauthorized"}`, logged as `auth outcome=unauthorized` at WARNING. An unset `SERVICE_TOKEN` rejects every request. Paths follow [ADR 0004](../docs/adr/0004-purchase-payments-communication.md), still to be confirmed by Purchase.

Path ids are positive integers up to 2147483647; anything else is `404`. Every error body is `{error}`.

### `POST /payments`
Body (JSON object): `booking_id`, `amount_cents` (positive integers), optional `currency` (`USD`), `card_number`, `expiry` (`MM/YY`), `cvc`, `idempotency_key` (required, 1-255 characters, not starting with `refund:`), optional `force_failure: true` (test hook; only a literal `true`).

Checks run in this order: body and non-card fields; then the idempotency key (so a retry is answered from the ledger even if the card has since expired); then the card; then whether the booking is already paid.

| Condition | Response |
|-----------|----------|
| Body not a JSON object, or a field invalid | `400 {error}`; nothing is recorded |
| Same `idempotency_key` seen before, same `booking_id` and `amount_cents` | Same status code and body as the first time (no second collection) |
| Same `idempotency_key`, different `booking_id` or `amount_cents` | `409 {error: "idempotency_key reused"}` |
| Invalid card | `400 {error}` (messages as in `src/domain/card.py`); nothing is recorded |
| Booking already has a `success` payment under a different key | `409` with the existing payment |
| `force_failure` | `402` and the recorded `failed` payment (`reason` `payment failed`) |
| Outcome cannot be determined | `202` and the recorded `unknown` payment (not produced while no provider is integrated) |
| Database failure | `500 {error: "payment unavailable"}`, logged at ERROR |
| Otherwise | `201` and the recorded `success` payment |

Concurrent requests are settled by the unique indexes: the same key records one row and both callers get it; different keys for one booking collect once and the other caller gets `409`.

A payment body is `{payment_id, booking_id, amount_cents, currency, status, card_last4, reason, created_at}` (`created_at` in UTC). The idempotency key is never returned.

### `GET /payments/<payment_id>`
`200` payment body; `404 {error: "payment not found"}`; `500` on a database failure. Used to resolve `unknown`.

### `GET /payments?booking_id=<id>`
`200 {payments: [...]}`, oldest first, including refunds; empty list for a booking without payments. `400 {error: "booking_id must be a positive integer"}`. Used for reconciliation.

### `POST /payments/<payment_id>/refund`
Body: optional JSON object with `reason` (non-empty string, default `cancellation`). Full amount only.

| Condition | Response |
|-----------|----------|
| Body malformed or not an object | `400 {error: "body must be a JSON object"}` |
| `reason` not a non-empty string | `400 {error: "reason must be a non-empty string"}` |
| Payment does not exist | `404 {error: "payment not found"}` |
| Payment is not `success` (including a refund row) | `409 {error: "payment is not refundable"}` |
| Already refunded (also the loser of a concurrent refund) | `200` the existing refund; its `reason` is unchanged |
| Database failure | `500 {error: "payment unavailable"}`, logged at ERROR |
| Otherwise | `201` a new `refunded` row with the original's `booking_id`, `amount_cents`, `currency` and `card_last4`; its `idempotency_key` is `refund:<payment_id>`. The original row is never changed. |

### Temporary: `POST /payment/bookings/<booking_id>/pay`
Stateless mock outcome moved from `spacey` PR #244 (PT-022, pinned at `0d4f4a1b4e29334884683de674bb17e18ed43466`); removed once Purchase calls `POST /payments`. Reads and writes no table and does not check the booking. A missing, malformed or non-object body counts as `{}`. Only ASCII digits match, with no trailing characters. `200 {booking_id, status: "success", card_last4}`; `400 {error}` with the first card problem; `402 {error: "payment failed"}` for `force_failure: true`.

### Proposed: notification to Purchase
After each recorded outcome Payments calls `POST {PURCHASE_URL}/bookings/<booking_id>/payment-result` with `{payment_id, status, amount_cents, occurred_at}` and `X-Service-Token`. A `2xx` means Purchase applied it or had already seen it. On a timeout or non-2xx Payments retries with backoff; a failed notification never changes the recorded payment. Purchase owns the endpoint and the booking update.

## Rules to preserve

1. A failed or unknown payment is never recorded as `success` ([ADR 0003](../docs/adr/0003-booking-after-failed-payment.md)).
2. Card data is validated before anything is written; only `card_last4` is persisted; no card data in logs.
3. Parameterised SQL only. Money is integer cents.
4. Log booking ids and fixed outcomes only, in the form `<event> booking_id=<id> outcome=<outcome>` (`payment_id=<id>` where no booking is known yet). Events: `payment` (`started`, `succeeded`, `replayed`, `failed`, `invalid_request`, `invalid_card`, `key_reused`, `already_paid`), `refund` (`started`, `refunded`, `already_refunded`, `invalid_request`, `not_found`, `not_refundable`), `payment_lookup`, `payment_list`, plus `database_error` for each. DEBUG for start events, INFO for success, WARNING for rejections, ERROR for database failures. Never log card data or database exception text. The level comes from `LOG_LEVEL`.

## Open / not built

- Agreement from Purchase on ADR 0004 (paths, fields, who sends card details).
- The notification to Purchase above, and `PURCHASE_URL` config.
- An `unknown` outcome: nothing produces one until a provider is integrated.
- `SERVICE_TOKEN` in the deployment (the Nomad job does not set it yet, so the deployed payment endpoints answer `401`).
- Removing the temporary `/payment/bookings/<id>/pay` once Purchase has switched.
