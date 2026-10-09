# Repository Guidelines

`spacey-payments` is the payments microservice of Spacey. It was split out of the `spacey` backend, which now calls it over HTTP. It owns the `payments` ledger (payment attempts and refunds). Paying a booking is the booking team's endpoint, not this service's. No provider is integrated. Subscriptions are out of scope and live elsewhere.

## Where things are

- Code: `src/app.py` is `create_app()`, which wires `config.py` (env vars), `db.py` (connection and migration runner), `logger.py` (the shared logger), `health.py` (`GET /health`) and the payments blueprint. `src/payments/` is the domain, split by layer: `api.py` (Flask blueprint, HTTP only), `services.py` (business rules, no Flask or SQL), `repository.py` (SQL only), `models/cards.py` (card validation). Keep each layer to its job.
- Migrations: `migrations/NNN_name.sql`, applied once each in filename order at startup and tracked in `schema_migrations`. Change the schema by adding a new numbered file, never by editing an applied one.
- Spec: `spec/payments/spec.md` is the contract (endpoints, status codes, rules; currently only `GET /health`). Read it before changing behaviour and update it in the same change. Decisions with trade-offs get an ADR in `spec/docs/adr/`.
- Related repo (sibling of this one): `../spacey` (backend, the caller of this service).
- Table: `payments` (`migrations/001_create_payments.sql`, `002_add_refunded_status.sql`). No foreign key to bookings: this service never touches bookings, which live elsewhere.

## Build, run and test

Python 3.10+, [uv](https://docs.astral.sh/uv/) and a running PostgreSQL.

- `uv sync`: install dependencies from `uv.lock`.
- `export DATABASE_URL='postgresql://spacey:spacey@localhost:5432/spacey'`: the default. The sibling `../spacey/compose.yaml` publishes Postgres on **5433**, so use that port if you start it with `docker compose up db -d`.
- `uv run flask --app 'src.app:create_app' run --port 5001 --debug`: start the server. Use 5001 because macOS AirPlay occupies 5000. Creating the app connects to the database and exits with a readable message if it cannot.
- `curl http://127.0.0.1:5001/health`: check app and database.
- `docker compose up --build`: run the service and its database in containers (service on 8001).
- `uv run python -m unittest discover -s tests`: run tests (needs `DATABASE_URL` pointing at a disposable database).

## Coding style

Four-space indentation, `snake_case`, uppercase constants, type hints and short docstrings as in the existing module. SQL is always parameterised with `%s` and separate parameters. Money is integer cents. No formatter or linter is configured; match the surrounding code.

## Testing

Tests live in `tests/test_*.py` with helpers in `tests/support.py`; add new ones there using `unittest` and Flask's test client, against a dedicated test database (`create_app(database_url, reset_on_start=True)`). Card validation is unit-tested in `tests/test_cards.py`. Cover every new endpoint's success and error paths, including idempotent retries and log levels.

## Security and configuration

- Never persist full card numbers or CVCs; store only the last four digits. Never log card data or database exception text.
- Treat the repo as public (the sibling repos are): no `.env`, credentials or tokens in commits.
- Variables: `DATABASE_URL`, `APP_REVISION` (reported by `/health`), `LOG_LEVEL`, `RESET_DB_ON_START`.
- `RESET_DB_ON_START=true` truncates the `payments` table. Use it only against disposable local or test data, never in a deployment.

## Workflow

Follow `spec/docs/process/CONTRIBUTING.md`: branch per change, pull request with what/why/how-checked, review before merge, no direct pushes to `main`. Commit subjects are short and descriptive. In PRs, list the validation commands you ran and include request/response examples for endpoint changes.

## Maintaining this file

Keep this file about how to work in this repo. Behaviour belongs in the spec. If the layout changes (new modules, Dockerfile, migrations, CI), update the sections above in the same PR.
