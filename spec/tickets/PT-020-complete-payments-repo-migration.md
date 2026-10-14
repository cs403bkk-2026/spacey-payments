# PT-020: Complete the migration from spacey to spacey-payments

Status: Open.
Date: 2026-10-09
Depends on: [PT-018](PT-018-split-payment-into-separate-service.md), [PT-019](PT-019-refactor-refund-logic-to-payments-service.md).
Related: [ADR 0003](../docs/adr/0003-booking-after-failed-payment.md), [ADR 0004](../docs/adr/0004-purchase-payments-communication.md), [payments spec](../payments/spec.md).
Owners: Payments and Purchase teams; each owns changes in its repository.

## Problem

PT-018 created `spacey-payments`; PT-019 added full refunds by payment ID.
The split is not complete: nothing in the new service records payment attempts,
refunds require seeded success rows, and Purchase still needs to call Payments
over HTTP. Service authentication and the deployment/data cutover also remain.
Moving files alone does not move the live payment flow or its ledger.

## Goal

A member can pay and cancel through Purchase while `spacey-payments` owns all
payment attempts and refunds. Purchase owns booking state and access decisions.
The services use separate databases; neither imports the other's domain code.
Retries and timeouts must not collect or refund twice.

## Scope and tasks

This ticket tracks the remaining migration across both repositories. Deliver
the work below in reviewable PRs, in dependency order; do not redevelop PT-019.

### 1. Agree the contract with Purchase

- Confirm ADR 0004's paths, payloads, status codes, card-data route and ownership.
- Define the operation key lifecycle: reuse a key after timeout/unknown; use a
  new key only after a confirmed failure. Reserve `refund:` for Payments.
- Agree callback retry limits, reconciliation cadence, and how cancellation
  pending a refund is represented and retried after a process restart.
- Update the ADR and spec before building against disputed fields.

### 2. Record and look up payment attempts in spacey-payments

- Implement `POST /payments`, `GET /payments/<payment_id>` and
  `GET /payments?booking_id=<id>` using the proposed spec.
- Preserve card shape/expiry validation and move the monolith's Luhn check.
  Validate positive integer cents and required identifiers at the HTTP boundary.
  Store only `card_last4`; never store or log full card numbers or CVCs.
- Persist success, failed and unknown outcomes. The payment ID must identify
  the same attempt on lookup and retry.
- Enforce idempotency and reject key reuse with a different booking or amount.
  Concurrent requests must not create duplicate attempts or two successful
  collections for one booking; a read-before-insert check alone is insufficient.
- Keep HTTP in `api.py`, rules in `services.py`, SQL in `repository.py` and
  schema changes in new numbered migrations.

### 3. Authenticate service calls

- Implement `X-Service-Token` checks for payment creation, lookup and refunds,
  and for Purchase's payment-result endpoint. Keep `/health` open.
- Configure `SERVICE_TOKEN`, `PURCHASE_URL` and `PAYMENTS_URL` in their owning
  services. Missing secrets must fail closed; never commit or log tokens.
- Use bounded HTTP timeouts and bounded backoff for idempotent retries.

### 4. Connect Purchase's pay flow and outcome handling

- Replace direct calls to `payment.services` with the agreed HTTP contract.
  Purchase supplies its recorded amount and checks booking eligibility/hold.
- Retain the payment ID and operation key needed for retry and reconciliation.
  A timeout means unknown; keep the booking unpaid and deny access until success
  is confirmed. Preserve the existing public booking API or document an agreed
  caller migration, including frontend changes if needed.
- Implement the `payment-result` callback and reconciliation from ADR 0004.
  Deduplicate callbacks and prevent stale results from overwriting newer state.
  A failed callback must not turn a successful payment into a failed one.
- If success arrives after the hold expires or the slot is lost, request the
  existing full-refund endpoint. Recovery must also work after a service restart.

### 5. Connect cancellation to PT-019 refunds

- Purchase resolves the original successful payment ID and calls
  `POST /payments/<payment_id>/refund`; it never inserts a refund locally.
- Unpaid and zero-cost subscription bookings need no monetary refund.
- Do not delete the only booking/payment reference before refund completion is
  confirmed or a durable pending-refund record is saved. Preserve enough state
  to retry after a timeout, crash or repeated cancellation request.
- Keep cancellation pending/failure visible to the caller; do not report a
  completed refund while its outcome is unknown. Payments never deletes bookings.

### 6. Cut over data, deployment and old code

- Inventory existing payment rows and booking-to-payment references. Write a
  cutover plan covering backup, ID/key preservation, verification, write
  ownership during cutover and rollback. Do not fabricate successful payment
  attempts for historical paid bookings without an agreed reconciliation rule.
- Check existing non-null idempotency keys for duplicates before migration 003;
  reconcile explicitly rather than deleting ledger history.
- Add the new service's CI test/build checks, deployment configuration, private
  service routing, secrets and health verification. Use a disposable test DB.
- Verify pay, lookup and refund with separate databases before removing old
  `spacey/payment/` code, imports, blueprint registration and startup migrations.
  Update affected tests, fixtures, API docs and configuration examples together.
- Retire the old ledger only after counts, amounts and references reconcile and
  the agreed backup/rollback plan is in place. No destructive table drop here.

## Acceptance criteria

- [ ] ADR 0004 and the payment contract are agreed with Purchase.
- [ ] A booking payment creates a real ledger attempt in `spacey-payments`;
  successful payment makes the eligible booking paid and enables access.
- [ ] Failed/unknown outcomes keep the booking unpaid and deny access.
- [ ] Same-operation retries and concurrent pay requests cannot collect twice;
  conflicting key reuse is rejected, and a confirmed failure allows a new attempt.
- [ ] Reconciliation resolves a timeout or lost callback after restart without
  creating another collection; duplicate/stale callbacks are safe.
- [ ] Paid cancellation creates exactly one full refund; repeated cancellation,
  concurrent requests and timeout recovery cannot create another refund.
- [ ] Late success after an expired hold is refunded; unpaid/zero-cost
  cancellation creates no refund row.
- [ ] Missing/invalid service tokens return `401` on protected endpoints;
  `/health` works without a token. Card data, tokens and DB diagnostics do not leak.
- [ ] Integration tests pass with two services and separate databases, including
  Payments downtime, callback failure and cancel/refund partial failure.
- [ ] Existing data and references reconcile under a reviewed cutover/rollback plan.
- [ ] CI passes; deployment health reports the intended revision; the old
  payment implementation has no remaining active callers.
- [ ] Specs, READMEs, environment examples and affected caller tests are updated.

## Out of scope

Real payment-provider integration, partial refunds, subscription billing,
message brokers, and deleting historical ledger data. An outbox may be a
separate follow-up if the agreed reconciliation strategy is insufficient.

## Risks and decisions needed

- ADR 0004 is still proposed; Purchase must confirm it before integration ships.
- PT-019 has no auth yet. Keep its endpoint private until task 3 is complete.
- HTTP cannot atomically commit changes across two databases. Cancellation and
  callback recovery need durable state or reconciliation, not only in-process retries.
- Existing bookings may be marked paid without a payment ledger row. Agree how
  those bookings are handled before enabling payment-ID-based refunds for them.
