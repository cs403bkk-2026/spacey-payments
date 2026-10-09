# PT-021: OpenAPI YAML for the payments service

Status: In progress. `openapi.yaml` is drafted and valid; review and sign-off pending.
Date: 2026-10-09
Owner: Tom
Depends on: [PT-018](PT-018-split-payment-into-separate-service.md) (service split).
Related: [PT-019](PT-019-refactor-refund-logic-to-payments-service.md) (refund endpoint, PR #3), PT-020, [ADR 0004](../docs/adr/0004-purchase-payments-communication.md), [payments spec](../payments/spec.md).

## Problem

The monolith documents its API in `openapi.yaml`, and the frontend relied on it. `spacey-payments` has no machine-readable contract: the request and response formats live only in `spec/payments/spec.md` and ADR 0004 prose. Purchase, which has to call this service over HTTP, needs one precise document for the paths, request bodies, response bodies and status codes.

## Scope

In:
- `openapi.yaml` (OpenAPI 3.0.3) at the repo root, in the style of the monolith's.
- Endpoints, with request and response schemas, examples and every status code:
  - `GET /health`
  - `POST /payment/bookings/{booking_id}/pay`: temporary stateless mock payment outcome, moved from `spacey` (PT-022); removed in the final API
  - `POST /payments`: start a payment attempt
  - `GET /payments?booking_id=`: list a booking's payments
  - `GET /payments/{payment_id}`: get one payment
  - `POST /payments/{payment_id}/refund`: full refund
- Shared schemas: `Payment`, `CreatePaymentRequest`, `RefundRequest`, `Error`.
- The `X-Service-Token` security scheme, with `/health` open.
- A status note in the description of what is implemented and what is only proposed.
- Keeping the file in sync with the spec and the code.

Out:
- Implementing any endpoint (PT-019 and later tickets).
- Booking-side endpoints, including Purchase's `payment-result` callback; those belong in Purchase's API document.
- Code generation, a documentation site, or contract tests against a running service.

## Contract summary

| Endpoint | Status | Responses documented |
|----------|--------|----------------------|
| `GET /health` | Implemented | `200`, `503` |
| `POST /payments/{payment_id}/refund` | Implemented in PT-019 (PR #3, in review) | `200`, `201`, `400`, `401`, `404`, `409`, `500` |
| `POST /payment/bookings/{booking_id}/pay` | **Temporary**: moved by PT-022 (source `spacey` PR #244, open); marked `deprecated`; replaced by `POST /payments` and removed in the final API | `200`, `400`, `401`, `402` |
| `POST /payments` | Proposed (ADR 0004) | `201`, `202`, `400`, `401`, `402`, `409`, `500` |
| `GET /payments?booking_id=` | Proposed (ADR 0004) | `200`, `400`, `401`, `500` |
| `GET /payments/{payment_id}` | Proposed (ADR 0004) | `200`, `401`, `404`, `500` |

Conventions in the file:
- A response body is the **Payment** `{payment_id, booking_id, amount_cents, currency, status, reason, card_last4, created_at}`. The idempotency key is stored but not returned.
- A repeat of a known `idempotency_key` returns the original status and body, so it has no response entry of its own.
- Errors are `{"error": "<message>"}`.
- The moved pay route returns a `PaymentOutcome` `{booking_id, status, card_last4}` and no `payment_id`, because it records nothing.
- Full card number and CVC are `writeOnly` and never appear in a response.

## Tasks

1. Draft `openapi.yaml` from the spec, ADR 0004 and the refund implementation in PR #3. Done.
2. Validate it as OpenAPI 3.0.3. Done (`openapi-spec-validator`).
3. Check the refund section against PR #3's code and tests: response fields, `400` messages, `reason` rules, `409` and repeat behaviour. Re-check once PR #3 is merged.
4. Review with Purchase: paths, fields and status codes, so they can build their client from it. Record any changes in ADR 0004 and the spec.
5. Link `openapi.yaml` from `README.md`, `AGENTS.md` and `spec/payments/spec.md`.
6. Add a rule to `AGENTS.md`: a change to an endpoint updates `openapi.yaml` in the same PR.
7. As each proposed endpoint lands, update its status in the description and compare the file with the implementation.

## Acceptance criteria

- [x] `openapi.yaml` exists at the repo root and validates as OpenAPI 3.0.3.
- [x] Every endpoint in the table above is documented with its parameters, request body, response schemas, examples and status codes.
- [x] The `Payment`, request and error schemas match the formats in the spec; the card number and CVC are write-only.
- [x] The description says which endpoints are implemented and which are proposed, and that authentication is not enforced yet.
- [ ] The refund section matches PR #3 as merged (fields, status codes, error messages).
- [ ] Purchase has reviewed the proposed endpoints and agreed or requested changes.
- [ ] `openapi.yaml` is linked from `README.md`, `AGENTS.md` and the spec, and `AGENTS.md` says to update it with endpoint changes.
- [ ] The "proposed" labels are removed from each endpoint as it is implemented and verified.
- [ ] The temporary `POST /payment/bookings/{booking_id}/pay` entry is removed from `openapi.yaml` once `POST /payments` replaces it.

## Validation

`uv run --no-project --with openapi-spec-validator python -I -c "import yaml; from openapi_spec_validator import validate; validate(yaml.safe_load(open('openapi.yaml')))"` passed on 2026-10-09 (OpenAPI 3.0.3). This checks the file's structure only; it does not prove the service behaves as documented.

## Risks

- Documenting endpoints that do not exist yet can mislead a client. Each is marked proposed in the file, and tasks 4 and 7 close that gap.
- The file can drift from the code. Task 6 makes the update part of every endpoint change; a contract test would be stronger and is a possible follow-up.
- Purchase has not agreed to the proposed paths and fields; they may change.
