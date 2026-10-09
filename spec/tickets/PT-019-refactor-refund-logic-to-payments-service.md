# PT-019: Refactor the refund logic back to the new repo

Status: Implemented; awaiting review.
Date: 2026-10-09
Depends on: [PT-018](PT-018-split-payment-into-separate-service.md) (service split).
Related: PT-013 (refund on cancellation, monolith PR #260), [ADR 0003](../docs/adr/0003-booking-after-failed-payment.md), [ADR 0004](../docs/adr/0004-purchase-payments-communication.md), [payments spec](../payments/spec.md).

## Problem

PT-013 added refund-on-cancellation to the `spacey` monolith (`payment/repository.py: insert_refund`, `payment/services.py: refund_cancelled_booking`, the `refunded` status). Payments now lives in `spacey-payments`, so that logic belongs here and Purchase should only ask for a refund over HTTP. Today this repo has the `payments` table and the `refunded` status (migrations `001`, `002`) but no refund code or endpoint.

## Scope

In:
- Move the refund logic from `spacey` into `spacey-payments`, following the layers: SQL in `payments/repository.py`, rules in `payments/services.py`, HTTP in `payments/api.py`.
- One endpoint, from ADR 0004: `POST /payments/<payment_id>/refund`. Optional `reason` (default `cancellation`); full amount only.

| Condition | Response |
|-----------|----------|
| Payment does not exist | `404 {error: "payment not found"}` |
| Payment is not `success` | `409 {error: "payment is not refundable"}` |
| Already refunded | `200` the existing refund row (idempotent) |
| Otherwise | `201` a new `refunded` row for the same `booking_id`, `amount_cents` and `card_last4`, `idempotency_key` = `refund:<payment_id>` |
| Database failure | `500 {error: "payment unavailable"}`, logged at ERROR |

- Logging in the `payment booking_id=… outcome=…` format; no card data or DB error text.
- Tests and spec update.

Out (remaining migration tracked in [PT-020](PT-020-complete-payments-repo-migration.md)):
1. `POST /payments`, `GET /payments/<id>`, `GET /payments?booking_id=`: recording and looking up payments.
2. Service-token auth (`X-Service-Token`) and `PURCHASE_URL` / `SERVICE_TOKEN` config.
3. The `payment-result` notification to Purchase.
4. Purchase side: `cancel_booking` calling this endpoint, and removing `payment/` refund code from `spacey`.

## Tasks

1. `repository.py`: `get_payment(db, payment_id)`, `get_refund_for_payment(db, payment_id)` (by key `refund:<payment_id>`), `insert_refund(db, payment)` reusing the shape of the monolith's `insert_refund`.
2. Migration `003_...`: unique index on `payments.idempotency_key` (where not null) so two concurrent refund requests cannot both insert; handle the conflict by returning the existing refund.
3. `services.py`: `refund_payment(db, payment_id, reason="cancellation")` returning `(payload, status)` with the table above; log each outcome.
4. `api.py`: register `POST /payments/<int:payment_id>/refund`.
5. Tests (see below).
6. Update `spec/payments/spec.md` (move this endpoint from Proposed to implemented) and `README.md` / `AGENTS.md` if the layout changes.

## Acceptance criteria

- [x] Refunding a `success` payment returns `201` and records exactly one `refunded` row with the same `booking_id`, `amount_cents`, `currency` and `card_last4`, `reason` set, and `idempotency_key` `refund:<payment_id>`.
- [x] Repeating the request returns `200` with the same refund and records no second row.
- [x] Two concurrent requests for the same payment record exactly one refund.
- [x] A `failed`, `unknown` or `refunded` payment returns `409` and records nothing.
- [x] An unknown `payment_id` returns `404`.
- [x] A database failure returns `500 {error: "payment unavailable"}` and logs `outcome=database_error` at ERROR without exception text.
- [x] The original `success` row is never modified.
- [x] No full card number or CVC appears in responses, logs or the database.
- [x] Tests pass against PostgreSQL (`uv run python -m unittest discover -s tests`).

## Tests

Seed `payments` rows directly (nothing records payments yet), then cover every row of the table above, the concurrent case, and log levels and fields.

## Validation

`DATABASE_URL=<disposable PostgreSQL 16 database> uv run python -m unittest discover -s tests -v`
passed all 11 tests on 2026-10-09, including concurrent refund requests using
separate database connections. Migrations 001–003 applied successfully to the
empty test database. `git diff --check` passed.

## Open question

The monolith refunded by `booking_id` and `amount_cents` straight from the cancelled booking row. ADR 0004 refunds by `payment_id`, which needs a `success` payment row to exist, and nothing writes those until ticket 1 of the follow-ups lands. Until then this endpoint can only be exercised with seeded rows. If the team wants refunds usable earlier, the alternative is `POST /refunds` with `{booking_id, amount_cents, card_last4, reason}`, which would change ADR 0004. Default for this ticket: follow ADR 0004.

## Risks

- Exposed without auth until follow-up 2 lands; do not deploy it publicly before then.
- Purchase has not agreed to ADR 0004; the path or fields may change.
