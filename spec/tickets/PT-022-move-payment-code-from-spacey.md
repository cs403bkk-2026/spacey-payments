# PT-022: Move the payment code from spacey into spacey-payments

Status: Implemented on this branch; awaiting review.
Date: 2026-10-12
Owner: Akarapong (Drake)
Source: [spacey PR #244](https://github.com/cs403bkk-2026/spacey/pull/244), pinned at
`0d4f4a1b4e29334884683de674bb17e18ed43466` (still unmerged).
Depends on: PT-018 (split), PT-020 (Unit of Work architecture).
Related: PT-019 (refund), PT-021 (OpenAPI), PT-023 (existing test migration),
PT-024 (final ledger endpoints), [ADR 0004](../docs/adr/0004-purchase-payments-communication.md).

## Implementation

The payment-owned half of PT-014 now lives in the current architecture:

- `src/routes/payment.py`: `POST /payment/bookings/<id>/pay`, behind the same
  `X-Service-Token` check as the other payment endpoints.
- `src/services/payment.py`: `authorize_booking_payment`. No session, repository,
  booking check, ledger write or callback.
- `src/domain/card.py`: full-string ASCII matching (`[0-9]` and `fullmatch`) so
  trailing newlines and non-ASCII digits are validation errors, not assertions.
- `tests/test_pay_booking.py` and `tests/test_card.py` cover the contract,
  including those digit checks.

No new dependency, schema or configuration is required.

## Preserved contract

Body: `card_number`, `expiry` (`MM/YY`), `cvc`, optional `force_failure`.
Missing, malformed and non-object JSON is treated as `{}`.

| Condition | Response |
|-----------|----------|
| Valid card | `200 {"booking_id":7,"status":"success","card_last4":"1111"}` |
| Invalid card | `400 {"error":"<validation message>"}` |
| Invalid/missing body | `400 {"error":"card_number must be 13-19 digits"}` |
| Valid card and literal `force_failure: true` | `402 {"error":"payment failed"}` |

First error wins: number shape → Luhn → CVC → expiry format → expired.
Messages: `card_number must be 13-19 digits`, `card_number is not a valid card number`,
`cvc must be 3 or 4 digits`, `expiry must be in MM/YY format`, `card has expired`.
The current UTC expiry month remains valid. Only `card_last4` leaves the service.

Logs use `payment booking_id=<id> outcome=<outcome>`: DEBUG `started`, INFO
`succeeded`, WARNING `invalid_card` or `failed`; never card values or bodies.

## Acceptance and checks

- [x] Exact success/error bodies and 200/400/402 status codes.
- [x] Missing/wrong-type fields, malformed/non-object JSON, invalid Luhn and expiry.
- [x] Full-string ASCII validation and validation-before-forced-failure order.
- [x] No ledger read or write. The route still requires `X-Service-Token`.
- [x] Log levels, fixed fields and absence of card data.
- [x] Spec, OpenAPI and ADR note the temporary route and the ASCII digit rule.

## Purchase handover and remaining work

Purchase checks booking existence/hold, calls the temporary route on this service,
and applies its result. Switching callers and deleting the monolith payment code
remain a separate Purchase PR.

Rebased onto main after PR #6, which already shipped the temporary route with the
ledger API. This branch keeps that one route and tightens card matching.

PT-024's `POST /payments` supersedes this route; remove it when Purchase switches.

## Limits

Stateless mock only: no money moves, no persistence and no retry protection.
Changes to PR #244 after the pinned source commit require another compatibility review.
