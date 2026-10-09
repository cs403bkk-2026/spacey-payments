# Project docs

| Folder | Contents |
|--------|----------|
| [`adr/`](adr/) | Architecture decision records. Numbered `NNNN-short-title.md`, never renumbered. |
| [`process/`](process/) | How the team works: [CONTRIBUTING](process/CONTRIBUTING.md) (branches, PRs, reviews, blockers). |
| [`operations/`](operations/) | [Load test results](operations/LOAD_TEST.md) and the team's [startup log](operations/STARTUP_LOG.md). |
| [`api/`](api/) | OpenAPI contract of the backend (`spacey`) that calls this service. (Payments' contract is in [`../payments/`](../payments/spec.md).) |
| [`overview/`](overview/) | Backend README: how to run the backend locally and how changes reach production. |

## ADRs

- [0001 Move reporting to Grafana](adr/0001-move-reporting-to-grafana.md)
- [0003 Booking after failed or unknown payment](adr/0003-booking-after-failed-payment.md)
- [0004 How Purchase and Payments communicate](adr/0004-purchase-payments-communication.md) (proposed)
