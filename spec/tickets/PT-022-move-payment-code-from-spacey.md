# PT-022: Move the payment code from spacey into spacey-payments

Status: Open.
Date: 2026-10-09
Owner: to be assigned
Source: the `spacey` repo (PRs authored by `0xAkarapong`).
Depends on: [PT-018](PT-018-split-payment-into-separate-service.md) (service split).
Related: [PT-019](PT-019-refactor-refund-logic-to-payments-service.md) (refund, already in this repo's PR #3), [PT-021](PT-021-openapi-yaml-for-payments-service.md) (OpenAPI), PT-020, [ADR 0003](../docs/adr/0003-booking-after-failed-payment.md), [ADR 0004](../docs/adr/0004-purchase-payments-communication.md), [payments spec](../payments/spec.md).

## Problem

The payment code was written inside the `spacey` monolith. Payments now lives in `spacey-payments`, so the payment-owned parts of that work belong here, behind HTTP, and should stop living in `spacey`'s `payment/` package. Only the refund part (PT-019) has moved so far.

## What payment code is in spacey

| PR | State | What it is | Belongs in |
|----|-------|------------|-----------|
| [#244](https://github.com/cs403bkk-2026/spacey/pull/244) PT-014, "hand payment outcomes to booking owner" (branch `pt-14-payment-booking-handoff`) | **Open**, not merged | `payment/api.py`: `POST /payment/bookings/<booking_id>/pay`. `payment/services.py`: `pay_booking(booking_id, body)`, `process_payment(...)`, a stateless mock outcome. `tests/test_payment_api.py`. Payment no longer reads or updates booking rows; Purchase owns existence checks, retries and the paid state. | **Move.** This is the payment half. |
| [#232](https://github.com/cs403bkk-2026/spacey/pull/232) PT-012, log payment outcomes without card data | Merged | `shared/logger.py` and the log calls and tests around `mark_booking_paid` (DEBUG started; INFO succeeded or already paid; WARNING invalid card, failed, not found; ERROR database failure). | The logging rules are **already here** (`src/logger.py`, spec rule 4). Port the payment-side tests only. The `mark_booking_paid` log calls are Purchase's. |
| [#230](https://github.com/cs403bkk-2026/spacey/pull/230) PT-003, booking behaviour after failed payment | Merged | The ADR. | **Already here** as `spec/docs/adr/0003-...`. |
| `payment/services.py` on `main` | Merged | `validate_card` with the **Luhn check**, `passes_luhn`, `authorize_card`. | **Move the Luhn check**; this repo's `models/cards.py` lacks it (an open item in the spec). |

## Behaviour to move (from PR #244)

`POST /payment/bookings/<booking_id>/pay`
- Body: `card_number`, `expiry` (`MM/YY`), `cvc`, optional `force_failure: true`.
- It reads no database and writes none, and it does not check that the booking exists.
- Success: `200 {"booking_id": 7, "status": "success", "card_last4": "1111"}`; only the last four digits are returned.
- Invalid card: `400 {"error": ...}` with `card_number must be 13-19 digits`, `card_number is not a valid card number` (Luhn), `cvc must be 3 or 4 digits`, `expiry must be in MM/YY format`, `card has expired`. The first problem found wins, in that order.
- Forced failure: `402 {"error": "payment failed"}`.
- A missing, malformed, or non-object JSON body is treated as `{}`, so it returns `400 card_number must be 13-19 digits`.

## Mapping

| From `spacey` (PR #244 / main) | To `spacey-payments` |
|---|---|
| `payment/api.py` `pay_booking` route | `src/payments/api.py` (the existing blueprint) |
| `payment/services.py` `pay_booking`, `process_payment`, `authorize_card` | `src/payments/services.py` |
| `payment/services.py` `passes_luhn`, Luhn step of `validate_card` | `src/payments/models/cards.py` |
| `tests/test_payment_api.py` | `tests/test_pay_outcome.py` (adapted) |
| `payment/tests/test_payment_logging.py` (payment-side cases) | `tests/` log tests |

Not moved: `purchase/booking.py` (`mark_booking_paid` and its logging), the removal of the `/bookings/<id>/confirmation/pay` route, the test that payment and purchase routes do not conflict, and `Dockerfile` / `shared/` changes. Those are Purchase's or `spacey`'s.

## Scope

In:
- Port the behaviour above into `spacey-payments` with the same inputs, outputs and status codes.
- Add the Luhn check to `models/cards.py`, with tests.
- Log each outcome in the `payment booking_id=… outcome=…` format: DEBUG `started`, INFO `succeeded`, WARNING `invalid_card` and `failed`. No card data in logs.
- Update `spec/payments/spec.md` and `openapi.yaml` (PT-021) for the moved endpoint.

Out:
- Recording payments in the `payments` ledger, idempotency keys and the `payment-result` callback (PT-020, ADR 0004).
- Auth between the services.
- Changes in `spacey`: switching Purchase to call this service and deleting `payment/` from the monolith. Those are a Purchase PR after this lands.

## Decision needed

PR #244 exposes `POST /payment/bookings/<booking_id>/pay` and returns a stateless outcome. ADR 0004 and `openapi.yaml` propose `POST /payments`, which records a ledger row and takes `amount_cents` and an `idempotency_key`. Default for this ticket: port #244 faithfully at its own path as a **temporary** route, so Purchase's code written against #244 keeps working, and replace it with `POST /payments` (PT-020), at which point the temporary route is removed. Then document the moved route in `openapi.yaml`, and mark in ADR 0004 and the spec that it is superseded when `POST /payments` ships.

## Tasks

1. Wait for, or pin, the final form of PR #244, since it is still open. Take the code from its head, not an older commit.
2. `models/cards.py`: add `passes_luhn` and the Luhn step to `validate_card`, in the order given above.
3. `services.py`: add `pay_booking(booking_id, body)` and `process_payment(...)`, with logging.
4. `api.py`: register `POST /payment/bookings/<int:booking_id>/pay` using `request.get_json(silent=True)`.
5. Tests, ported and adapted (below).
6. Update `spec/payments/spec.md`, `openapi.yaml` and `README.md`.
7. Hand over to Purchase: a note on the route, body and status codes, so they can point `spacey` at this service and remove `payment/` from the monolith.

## Acceptance criteria

- [ ] A valid card returns `200` with exactly `{booking_id, status: "success", card_last4}`; no number, expiry or CVC.
- [ ] Each invalid-card case returns `400` with the message above, and an invalid Luhn number is rejected.
- [ ] `{"card_number": "4111111111111111"}`-style bodies missing other fields are rejected with the first error found.
- [ ] `force_failure: true` returns `402 {"error": "payment failed"}`.
- [ ] `null`, `[]`, `"card"`, `42`, `true` and malformed JSON bodies return `400 card_number must be 13-19 digits`.
- [ ] The endpoint reads and writes no database table, and does not check that the booking exists.
- [ ] No card number, expiry or CVC appears in a response beyond `card_last4`, or in any log line.
- [ ] Log levels and fields match the spec.
- [ ] Tests pass against PostgreSQL (`uv run python -m unittest discover -s tests`).

## Tests (ported from `tests/test_payment_api.py` and `payment/tests/test_payment_logging.py`)

- Success returns only the payment outcome.
- The invalid-card table: missing, malformed or failing-Luhn number, bad or missing expiry, expired, bad or missing CVC.
- Non-object and malformed JSON bodies.
- Forced failure.
- Log levels per outcome, and that card values never appear in logs.
- Luhn unit tests in `tests/test_cards.py`.
- Dropped as `spacey`-only: the removed confirmation route and the payment-vs-purchase route conflict.

## Risks

- PR #244 is not merged. If it changes, the ported code and this ticket change with it.
- The moved endpoint persists nothing, so nothing here prevents a double collection. Retry safety arrives with the ledger and idempotency keys (PT-020).
- Two ways to pay (`/payment/bookings/<id>/pay` and the proposed `POST /payments`) for a while. The default above keeps this short-lived; if it is not, one of them should be dropped.
- Not authenticated until the service-token ticket lands; keep it private until then.
