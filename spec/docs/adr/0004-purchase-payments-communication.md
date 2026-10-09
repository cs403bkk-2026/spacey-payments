# ADR 0004: How Purchase and Payments communicate

Date: 2026-10-09

Status: Proposed. The booking team (Purchase) has not agreed to the paths and fields below; only the refund endpoint is implemented (without service auth). The remaining integration is split into follow-ups; refunds are tracked in: [PT-019](../../tickets/PT-019-refactor-refund-logic-to-payments-service.md).

## Context

Purchase (bookings, access) and Payments are separate services with separate databases. [ADR 0003](0003-booking-after-failed-payment.md) fixes who owns what and lists the integration details left open: request and notification paths, payment IDs, duplicate handling, redelivery, unknown outcomes and refunds. This ADR picks the transport and fills in those details.

## Decision

Use **synchronous HTTP/JSON in both directions**. No shared database, no message broker, no gRPC.

- Purchase calls Payments to start a payment, look one up, or refund it.
- Payments calls a Purchase-owned endpoint to report the outcome. Purchase applies it; Payments never writes booking rows.
- Every call is idempotent, so a retry can never collect or refund twice.

Alternatives considered:

| Option | Why not (now) |
|--------|---------------|
| Message queue / event bus | Sturdier delivery, but a new piece of infrastructure to run for two services. Revisit if more consumers appear (receipts, reporting, access events). |
| HTTP plus an outbox in Payments | Closes the crash-between-record-and-notify gap without a broker. A good later upgrade; see Consequences. |
| gRPC | Typed and fast, but adds tooling to a Flask/JSON team for no load benefit. |
| Shared database | Defeats the split. |

## Contract

The Payments side is specified in [`payments/spec.md`](../../payments/spec.md). In summary:

**Purchase → Payments**

| Call | Purpose |
|------|---------|
| `POST /payments` | Start a payment attempt for a booking, with the recorded `amount_cents` and an `idempotency_key`. |
| `GET /payments/<payment_id>` | Resolve an `unknown` outcome: ask about the same operation, never collect again. |
| `GET /payments?booking_id=<id>` | Reconcile a booking's payments. |
| `POST /payments/<payment_id>/refund` | Full refund: cancellation (PT-013) and late success after the hold expired. |

**Payments → Purchase** (Purchase owns this endpoint)

`POST {PURCHASE_URL}/bookings/<booking_id>/payment-result` with `{payment_id, status, amount_cents, occurred_at}`. Purchase answers `2xx` for a result it has applied *or already seen*.

**Rules**

1. Purchase checks the 15-minute hold before calling `POST /payments`. Payments has no expiry timer.
2. Pressing Pay again after a confirmed failure sends a new `idempotency_key` and gets a new `payment_id`. A retry of the *same* operation (timeout, unknown) reuses the key and gets the same payment back.
3. A timeout or connection error from Payments is `unknown` to Purchase, not `failed`. Purchase keeps the booking unpaid, grants no access, and resolves it with `GET /payments/<id>` or the same `POST` with the same key.
4. Late success: Payments records `success` as normal. If the hold has expired or the slot is gone, Purchase requests the refund.
5. Notification failure is not collection failure. The payment stays as recorded; only the notification is retried.
6. Purchase dedupes results by `payment_id` and ignores a result older than what it already applied (`occurred_at`), so an old result cannot overwrite a newer booking decision.
7. Service-to-service calls carry `X-Service-Token`, a shared secret from the environment. `/health` is open. No card data in logs on either side.
8. Timeouts are short (about 5 s) and retries use backoff. Only idempotent calls are retried.

## Consequences

- Simple to build, run and debug with `curl`; both teams already work in Flask and JSON.
- Payments retries the callback in process. If Payments crashes after recording a payment but before Purchase acknowledges, the notification is lost. The safety net is reconciliation: Purchase polls `GET /payments?booking_id=` for bookings stuck unpaid with an `unknown` or in-flight payment. If that proves too weak, add an outbox table in Payments that a worker drains, without changing the contract.
- Both services need each other's base URL and the shared token in configuration (`PURCHASE_URL`, `SERVICE_TOKEN` in Payments; `PAYMENTS_URL`, `SERVICE_TOKEN` in Purchase).
- Card details should go from the frontend straight to Payments where possible. If they pass through Purchase, Purchase must not log or store them. This is still to be agreed.

## Still to agree with Purchase

- Exact path and fields of `payment-result` and how Purchase answers an expired hold.
- Who sends card details, and from where.
- Retry limits for the callback and the reconciliation interval.
- Whether refunds may ever be partial (this ADR assumes full refunds only, per ADR 0003).
