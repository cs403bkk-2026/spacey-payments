# ADR 0001: Move reporting to Grafana

Date: 2026-10-02

Status: Accepted decision; implementation and live verification pending.

## Context

Spacey currently calculates business metrics in `app.py` and presents them in
its own HTML dashboard. The same calculations serve the `/metrics` JSON API.
Maintaining that presentation adds code alongside the booking, payment and
access behaviour.

Reporting is a **supporting domain**: it helps people understand and operate
the business, but a custom reporting interface is not what differentiates
Spacey's member journey. The business still needs accurate reports. It does
not need to build every part of their presentation itself.

Grafana is already available on the platform. Using it offers a way to reduce
custom application code and focus development effort on the member journey.
This is a choice for the current reporting needs, not a rule that every
supporting domain must be moved out of an application.

## Decision

Use Grafana as the external system for the read-only business reporting
dashboard. Here, external means outside the Spacey application; it does not
require a third-party hosted service.

- Reproduce the existing ten summary metrics and revenue-by-space view with
  equivalent meaning. Pixel-identical presentation is unnecessary.
- Keep booking, payment, access and transactional operator controls in their
  owning applications. Grafana reads reporting data; it does not change it.
- Keep dashboard definitions, provisioning, the reporting data contract and
  reconciliation tooling versioned in `cs403bkk-cluster-jobs`, alongside the
  Grafana deployment configuration. Spacey retains this architectural record
  and the application integration.
- Expose aggregate reporting views through narrowly scoped read-only database
  access. Do not give the reporting connection general access to service
  tables or write privileges. Keep credentials outside Git.
- After the replacement is verified, direct application reporting navigation
  and `/dashboard` to Grafana and remove the redundant HTML presentation.
  Retain `/metrics` and `compute_metrics()` for API compatibility and as the
  reconciliation reference. Removing them requires a separate caller and
  compatibility assessment.

The reporting definitions remain business decisions even when Grafana renders
them. Preserve their units, time windows, denominators and existing behaviour
for empty data. In particular, revenue means the sum of paid bookings' amounts,
not independently verified collected money; members means distinct booking
member values. Keep these qualifications and the test-data notice visible.

## Alternatives considered

| Alternative | Benefit | Reason for not choosing it now |
| --- | --- | --- |
| Keep the HTML dashboard in Spacey | One application and no migration | Retains custom presentation code for a supporting need already served by Grafana. |
| Build a separate custom reporting service | Independent implementation and deployment | Still requires building and operating a custom reporting product. |
| Use Grafana | Reuses an available reporting system and removes custom presentation work | Chosen, accepting the integration, access and operational costs below. |

## Consequences

We expect less reporting UI code to maintain and more development time for the
member journey. These are expected benefits, not measured outcomes yet.

This removes custom reporting presentation, not all reporting code: retaining
`/metrics` and `compute_metrics()` preserves compatibility but leaves a
reconciliation obligation between application calculations and Grafana queries.
Removing the old HTML report also removes a fallback, so recovery must preserve
a usable report rather than merely revert a deployment specification.

The replacement introduces a dependency on Grafana availability and login.
Moving presentation does not remove dependence on the underlying data or
guarantee isolation from database failures. Reporting queries can still add
load to the database.

The platform configuration and application schema must evolve together.
Reconciliation checks live outside Spacey's CI, so a green Spacey build alone
does not establish reporting compatibility. Changes to data ownership or
metric definitions must include the reporting contract and its checks.

Access must be checked at the data boundary as well as the dashboard. The
owner has accepted student Grafana Editor access for this migration; restricting
a folder alone does not make the datasource operator-only. This decision does
not claim that the separate operator-access issue is complete.

## Migration and verification

### Work to be done

The following checklist tracks remaining delivery and evidence, not completion
of this ADR. Leave items open until the corresponding result is recorded in
[#207](https://github.com/cs403bkk-2026/spacey/issues/207) or its linked changes.

- [ ] Platform/reporting implementation: version and release the dashboard,
  provisioning, aggregate views and narrowly scoped read-only grants.
- [ ] Reporting validation: reconcile the ten summary metrics and revenue by
  space, including the boundary/error cases below, at recorded revisions.
- [ ] Access verification: check the intended user journey, datasource permissions
  and unauthorised-access denial; record campus-network evidence or its absence.
- [ ] Application cleanup: after the acceptance checks, review and release #211,
  redirect reporting navigation and remove the redundant HTML presentation.
  Retain `/metrics` and `compute_metrics()` until separately assessed.
- [ ] Release/recovery verification: recheck reporting and the member journey,
  and exercise the rollback procedure below with a working report preserved.
- [ ] Handover: identify who maintains metric definitions, reporting-contract
  checks and Grafana configuration, and record how schema changes reach them.

These are responsibilities to assign through the existing work items, not new
team appointments. The operator-access and time-series follow-ups remain
separate; this checklist does not claim they are complete.

### Acceptance and recovery procedure

1. Release the reviewed Grafana configuration and read-only data contract while
   keeping the existing application report available.
2. Reconcile all ten metrics and revenue by space against the existing
   calculations and known records. Compare the same data and time window;
   explain any difference before accepting it. Check empty data, zero
   denominators, paid and unpaid bookings, and bookings crossing the utilisation
   window. A failed query must appear as an error, not a valid zero.
3. Verify intended users can reach the dashboard and query the permitted data,
   and that unauthorised access is denied. Exercise the University-network
   journey when available; record it as unrun if it cannot be exercised.
4. Record checked application/configuration revisions and live results. Only
   then may the removal preparation in PR #211 proceed through its normal
   review and merge gates. Preparing the PR is not permission to merge it.
5. Verify the reporting navigation and the booking, payment and access journey
   after the application change.

Rollback must preserve a working user-facing report. If the application already
redirects to Grafana, first restore and verify the application report or a
working alternative target before deleting the Grafana report. Platform rollback
must explicitly remove the provisioned datasource and folder, verify their
absence, and restore the recorded prior deployment specification. A plain job
revert is insufficient. Database-object cleanup is a separate later action.

This ADR records the decision and its acceptance conditions. It does not claim
that deployment, live parity, access, rollback or campus-network checks have
passed. Additional time-series reporting remains separate scope.

## References

- [Reporting migration and acceptance criteria — #207](https://github.com/cs403bkk-2026/spacey/issues/207)
- [Application removal preparation — #211](https://github.com/cs403bkk-2026/spacey/pull/211)
- [Existing reporting implementation at da18646](https://github.com/cs403bkk-2026/spacey/blob/da18646051da8097782046518acd7b61231d4abc/app.py)
- [Time-series follow-up — #139](https://github.com/cs403bkk-2026/spacey/issues/139)
- [Operator-access follow-up — #179](https://github.com/cs403bkk-2026/spacey/issues/179)
- [Decision discussion in Buzz](buzz://message?channel=d0b3a679-8e7e-4430-abca-0a09ef6c504e&id=ec96d462b814e2b2ef48983e4248c2e9001ab27898b5f1b958f2f0d310e4d0bb)
- [Owner's request to record the supporting-domain rationale](buzz://message?channel=d0b3a679-8e7e-4430-abca-0a09ef6c504e&id=24f229bf13bfde7cb15c34810562cb3e93798cf4859cd457c98a975a9f3462c2)
