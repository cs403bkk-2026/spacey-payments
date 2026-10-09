# ADR 0003: Booking after failed or unknown payment (PT-003)

Date: 2026-10-06

Status: Records the supplied Payment/Purchase agreement; implementation is not
verified by this document.

## Problem

A failed payment does not establish that a booking is paid. An unknown result
may hide a successful collection. Purchase and Payments need an explicit
boundary so that retries do not collect twice and reservation expiry does not
silently discard a successful payment.

## Decision and responsibilities

Purchase owns the booking, its recorded price, reservation eligibility, and the
unpaid hold. Payments processes collection and records and returns its outcome.
The target boundary gives Payments no booking expiry timer and no responsibility
for changing booking rows or releasing intervals.

| Outcome | Payments | Purchase |
| --- | --- | --- |
| Failed | Reports failure | Keeps the booking unpaid and retryable at its recorded price while the hold is active |
| Unknown | Checks or retries the same operation without another collection | Keeps payment unconfirmed; does not grant access |
| Success | Records and returns normal success | Applies the result according to booking eligibility; coordinates access for a confirmed paid booking |

Purchase confirmed, as relayed by the PT-003 owner on 2026-10-06, that after
a failed payment the booking stays unpaid and retryable while its 15-minute
hold is active. This confirms the failed-payment policy, not implementation
completion or the remaining request/reconciliation contract.

A failed attempt alone does not cancel the booking or release its interval.
A repeat of a successful operation must not collect again.

## Payment attempt and outcome notification

The supplied discussion notes add these integration decisions:

- The member initiates payment by pressing Pay in Frontend. A payment attempt
  is created and Payments processes it. The request routing and placement of
  Purchase's pre-collection hold check still need an explicit API contract.
- When the member presses Pay again after a confirmed failure, Payments creates
  a new payment ID for the same booking. Failure alone does not automatically
  create another attempt. The new Pay action does not create a new booking or
  restart the hold.
- Payments calls a Purchase-owned API to notify it of success or failure.
  Purchase implements that API and owns the booking update; Payments does not
  write Purchase's booking rows directly.

A new attempt after failure differs from resolving an unknown result or
repeating a successful operation. The latter must refer to the same operation
and must not create another collection. How a repeated Frontend request is
recognized before creating a new payment ID remains to be specified.

If collection finishes but notification to Purchase fails, that notification
failure must not be mistaken for a failed collection. Outcome redelivery,
acknowledgement, and duplicate handling still need agreement. This document
records the required boundary, not an implemented delivery mechanism.

## Reservation expiry and late success

According to the supplied Purchase clarification, Purchase owns the 15-minute
hold measured from booking creation. Retries do not restart the timer. Purchase
checks the hold before requesting collection; Payments has no booking expiry
timer.

If collection succeeds late, Payments records and returns normal success.
Purchase decides whether the booking still exists and its slot is free. It
confirms the booking if allowed; otherwise it requests a full refund from
Payments. This document does not define how an expired or removed booking is
restored or confirmed.

Collection outcome and reservation eligibility are separate decisions. Payments
must not change a successful collection into failure merely because Purchase's
hold has expired. Purchase's pre-collection check alone cannot prevent a result
from arriving after expiry, so the late-success path is still necessary.

Purchase referenced moving the expiry logic from #225 into its `purchase/`
module. This is their reported preparation task; no code or completion of that
move was verified for this document.

## Remaining implementation contract

- Agree collection and Purchase-notification API paths, request/result fields,
  and error responses, including the booking reference and recorded amount.
- Place Purchase's hold check before collection in the Frontend-initiated flow.
- Specify how requests refer to payment IDs and how duplicate requests are
  identified; pressing Pay again after confirmed failure creates a new ID, while unknown/success
  resolution refers to the same operation.
- Agree acknowledgement and redelivery when notifying Purchase fails, with
  duplicate outcome handling that cannot collect twice or overwrite a newer
  booking decision with an older result.
- Specify how unknown outcomes are checked and how a late success and resulting
  refund request are delivered and processed without duplicate collection or
  refund.
- Purchase owns the exact deadline check and how it safely confirms a booking
  when checking availability, including concurrent reservations.

These details require follow-up contracts; this ADR does not invent API fields
or claim that reconciliation, idempotency, or refunds already work.

## Scope and validation

Documentation only. No changes to Purchase files, payment code, APIs, schema,
or runtime behavior. Moving existing booking writes out of Payments is PT-014;
refund implementation is PT-013. The full provider contract is PT-002.

Review scenarios for the follow-up implementation:

- Failure retains an unpaid booking and its price during the active hold;
  failure alone creates no new attempt. Pressing Pay again after confirmed
  failure creates a new payment ID for that booking.
- Success and failure are notified through Purchase's API, with booking updates
  performed by Purchase rather than Payments.
- Failed outcome notification does not trigger another collection; duplicate
  notification handling follows the agreed delivery contract.
- A retry does not extend the hold; Purchase checks it before collection.
- Unknown is resolved as the same operation without a second collection.
- Late success is recorded as success; Purchase either confirms the booking if
  allowed or requests a full refund.
- Repeating success or refund processing does not move money twice.

This PR checks documentation and whitespace only. These scenarios are acceptance
requirements, not executed tests or deployment evidence.

## Sources

- User-supplied discussion screenshot on 2026-10-06: Frontend initiates payment,
  pressing Pay again after failure creates a new payment ID, and Payments notifies Purchase
  through Purchase's API for booking updates, including failure.
- Purchase confirmation of unpaid, retryable bookings after failed payment,
  relayed by the PT-003 owner on 2026-10-06; no original discussion URL supplied.
- The user-supplied agreement, section 5, "Reservation expiry and late success":
  attributed to Purchase's clarification. Its original discussion URL was not
  supplied; this document does not claim independent verification of that source.
- [SP-R06, SP-R07 and Q5](https://github.com/cs403bkk-2026/spacey-business-rules/blob/main/RULES.md).
  The supplied clarification resolves the clock-start question for this agreement;
  implementation details listed above remain to be agreed.
- [Payments scope #199](https://github.com/cs403bkk-2026/spacey/issues/199) and
  [Purchase scope #198](https://github.com/cs403bkk-2026/spacey/issues/198).
- [Earlier PT-003 documentation #224](https://github.com/cs403bkk-2026/spacey/pull/224)
  and [withdrawn implementation #225](https://github.com/cs403bkk-2026/spacey/pull/225).
