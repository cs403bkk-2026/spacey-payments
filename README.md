# spacey-payments

Payments microservice for Spacey. Owns the `payments` ledger: payment attempts and refunds, called by Purchase over HTTP. No payment provider is integrated.
The contract is in [`spec/payments/spec.md`](spec/payments/spec.md) and [`openapi.yaml`](openapi.yaml); contributor
and agent guidance is in [`AGENTS.md`](AGENTS.md).

## Layout

```
src/app.py            create_app(): connects, runs migrations, wires blueprints
src/config.py         environment variables
src/database.py       Postgres engine, sessions and the migration runner
src/unit_of_work.py   one transaction per request; hands out Services
src/logger.py         the shared logger (no card data in logs)
src/routes/           HTTP only: health.py, payment.py (+ X-Service-Token check)
src/services/         business rules: payment.py, health.py, services.py
src/repositories/     SQL only: payments.py
src/models/           SQLAlchemy model: payment.py
src/domain/           card.py (card validation, Luhn)
src/result.py         Result type returned by services and repositories
migrations/           numbered SQL, applied once each at startup
tests/                unittest + Flask test client, real PostgreSQL
spec/                 service spec and project docs
openapi.yaml          HTTP contract
Dockerfile            gunicorn image
compose.yaml          Postgres (5433) + the service (8001)
```

## Run locally

```sh
docker compose up db -d
uv sync
export DATABASE_URL=postgresql://spacey:spacey@localhost:5433/spacey
export SERVICE_TOKEN=local-dev-token
uv run flask --app 'src.app:create_app' run --port 5001 --debug
curl http://127.0.0.1:5001/health
curl -H 'X-Service-Token: local-dev-token' 'http://127.0.0.1:5001/payments?booking_id=42'
```

Whole stack in containers: `docker compose up --build`, then `http://127.0.0.1:8001/health`.

## Test

```sh
docker compose exec db createdb -U spacey spacey_payments_test   # once
export DATABASE_URL=postgresql://spacey:spacey@localhost:5433/spacey_payments_test
uv run python -m unittest discover -s tests
```

Tests wipe the `payments` table: use a disposable database.

## Configuration

| Variable | Purpose | Default (local only) |
|----------|---------|----------------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://spacey:spacey@localhost:5432/spacey` |
| `APP_REVISION` | Reported by `/health` | `local` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. Payment start events are DEBUG; success is INFO; rejections WARNING; database failures ERROR. | `INFO` |
| `SERVICE_TOKEN` | Shared secret Purchase sends as `X-Service-Token`. Unset: every endpoint except `/health` answers `401`. | none (compose sets `local-dev-token`) |
| `RESET_DB_ON_START` | `true` truncates `payments` on start. Never in a deployment. | `false` |

See `.env.example`. Never commit `.env` or credentials.

## Deploy

The manual [release workflow](.github/workflows/release.yml) tests, publishes and deploys a reviewed `main` revision to the course Nomad cluster when explicitly enabled. Service address, deployed revision, platform setup and the SRE check: [`spec/docs/operations/DEPLOYMENT.md`](spec/docs/operations/DEPLOYMENT.md).
