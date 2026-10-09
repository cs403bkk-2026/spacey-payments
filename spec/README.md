# Spacey spec

Specifications and project documentation for the Spacey system, which is split across repositories:

| Repo | Role |
|------|------|
| `spacey` | Backend JSON API (spaces, bookings, access, accounts, metrics) |
| `spacey-payments` | Payments microservice (being split out of `spacey`) |

## Layout

```
spec/
  README.md          this file
  payments/          what the payments service must do (the contract)
  docs/              everything else about the project - see docs/README.md
```

- **`payments/`** is the *spec*: behaviour, API contract and rules a change must respect. Write or update it **before** implementing.
- **`docs/`** is the project record: decisions (ADRs), process, operations, API references and overviews.

## Working rules

- A behaviour change starts as a change to the spec (or a new ADR in `docs/adr/` if it is a decision with trade-offs), then code.
- Cross-service agreements (e.g. Purchase calls Payments) belong here, not in only one repo.
- Copies of repo files in `docs/` (READMEs, `openapi.yaml`, CONTRIBUTING) are **snapshots taken 2026-10-09**. Until a file is moved for good, the original in its repo is the source of truth; update that and re-copy.
