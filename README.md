# spacey-payments

Payments microservice for Spacey. Mocked: no payment provider is integrated.
The contract is in [`spec/payments/spec.md`](spec/payments/spec.md); contributor
and agent guidance is in [`AGENTS.md`](AGENTS.md).

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
.github/workflows/    test, then build image on main
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

Tests wipe the `bookings` table: use a disposable database.

## Configuration

| Variable | Purpose | Default (local only) |
|----------|---------|----------------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://spacey:spacey@localhost:5432/spacey` |
| `APP_REVISION` | Reported by `/health` | `local` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. Payment start events are DEBUG; success is INFO; rejections WARNING; database failures ERROR. | `INFO` |
| `RESET_DB_ON_START` | `true` truncates `bookings` on start. Never in a deployment. | `false` |

See `.env.example`. Never commit `.env` or credentials.
