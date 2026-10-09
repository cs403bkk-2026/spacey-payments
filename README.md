# spacey-payments

Payments microservice for Spacey. Owns the `payments` ledger; paying a booking is the booking team's endpoint, not this service's. No payment provider is integrated.
The contract is in [`spec/payments/spec.md`](spec/payments/spec.md); contributor
and agent guidance is in [`AGENTS.md`](AGENTS.md).

## Refunds

`POST /payments/<payment_id>/refund` records a full mock refund of an existing
successful payment. Send an optional `{"reason": "cancellation"}` JSON body.
Returns `201` on creation, `200` with the same refund on retries, `404` for an
unknown payment, `409` for a non-success payment, `400` for invalid input, or
`500` if the database is unavailable. Concurrent retries create one ledger row.
No payment provider is integrated, and payment creation and Purchase integration
are separate follow-ups: seed success rows to exercise this endpoint for now.

Authentication is not implemented; keep the service private until service auth
lands. Migration 003 requires unique existing non-null idempotency keys and
fails rather than deleting duplicates. See the [contract](spec/payments/spec.md).

## Layout

```
src/app.py            create_app(): wires config, db, logger, blueprints
src/config.py         environment variables
src/db.py             connection + migration runner
src/logger.py         the shared logger (no card data in logs)
src/health.py         GET /health
src/payments/         api.py (HTTP) -> services.py (rules) -> repository.py (SQL),
                      models/cards.py (card validation)
migrations/           numbered SQL, applied once each at startup
tests/                unittest + Flask test client, real PostgreSQL
spec/                 service spec and project docs
Dockerfile            gunicorn image
compose.yaml          Postgres (5433) + the service (8001)
```

## Run locally

```sh
docker compose up db -d
uv sync
export DATABASE_URL=postgresql://spacey:spacey@localhost:5433/spacey
uv run flask --app 'src.app:create_app' run --port 5001 --debug
curl http://127.0.0.1:5001/health
```

Whole stack in containers: `docker compose up --build`, then `http://127.0.0.1:8001/health`.

## Test

```sh
export DATABASE_URL=postgresql://spacey:spacey@localhost:5433/spacey
uv run python -m unittest discover -s tests
```

Tests wipe the `payments` table: use a disposable database.

## Configuration

| Variable | Purpose | Default (local only) |
|----------|---------|----------------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://spacey:spacey@localhost:5432/spacey` |
| `APP_REVISION` | Reported by `/health` | `local` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. Payment start events are DEBUG; success is INFO; rejections WARNING; database failures ERROR. | `INFO` |
| `RESET_DB_ON_START` | `true` truncates `payments` on start. Never in a deployment. | `false` |

See `.env.example`. Never commit `.env` or credentials.
