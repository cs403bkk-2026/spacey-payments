# Repository Guidelines

`spacey-payments` is the payments microservice of Spacey. It was split out of the `spacey` backend, which now calls it over HTTP. It owns the `payments` ledger (payment attempts and refunds). The booking's paid state belongs to Purchase. No provider is integrated. Subscriptions are out of scope and live elsewhere.

## Where things are

- Code: `src/app.py` is `create_app()`: it connects (`database.py`, which also runs migrations), and registers the blueprints. One request is one `UnitOfWork` transaction (`unit_of_work.py`) that hands out `Services`. Layers: `routes/` (Flask blueprints, HTTP only, including the `X-Service-Token` check), `services/` (business rules and outcome logging, no Flask or SQL), `repositories/` (SQL only, returning `Result`), `models/payment.py` (SQLAlchemy model), `domain/card.py` (card validation). `config.py` holds env vars and `logger.py` the shared logger. Keep each layer to its job.
- Migrations: `migrations/NNN_name.sql`, applied once each in filename order at startup and tracked in `schema_migrations`. Change the schema by adding a new numbered file, never by editing an applied one.
- Deployment: `deploy/payments.nomad.hcl` (Nomad job) and `.github/workflows/release.yml` (manual release from `main`: tests, image smoke test, GHCR publish, deploy, public `/health` check). Address, revision and setup: `spec/docs/operations/DEPLOYMENT.md`.
- Spec: `spec/payments/spec.md` is the contract (endpoints, status codes, rules) and `openapi.yaml` its machine-readable form. Read them before changing behaviour and update both in the same change. Decisions with trade-offs get an ADR in `spec/docs/adr/`.
- Related repo (sibling of this one): `../spacey` (backend, the caller of this service).
- Table: `payments` (`migrations/001_create_payments.sql`, `002_add_refunded_status.sql`, `003_add_payment_unique_indexes.sql`). No foreign key to bookings: this service never touches bookings, which live elsewhere.

## Build, run and test

Python 3.10+, [uv](https://docs.astral.sh/uv/) and a running PostgreSQL.

- `uv sync`: install dependencies from `uv.lock`.
- `export DATABASE_URL='postgresql://spacey:spacey@localhost:5432/spacey'`: the default. The sibling `../spacey/compose.yaml` publishes Postgres on **5433**, so use that port if you start it with `docker compose up db -d`.
- `uv run flask --app 'src.app:create_app' run --port 5001 --debug`: start the server. Use 5001 because macOS AirPlay occupies 5000. Creating the app connects to the database and exits with a readable message if it cannot.
- `curl http://127.0.0.1:5001/health`: check app and database.
- `docker compose up --build`: run the service and its database in containers (service on 8001).
- `uv run python -m unittest discover -s tests`: run tests (needs `DATABASE_URL` pointing at a disposable database, e.g. `spacey_payments_test`).

## Coding style

Four-space indentation, `snake_case`, uppercase constants, type hints and short docstrings as in the existing module. SQL is always parameterised: SQLAlchemy expressions or `text()` with bound `:name` parameters, never string formatting. Money is integer cents. No formatter or linter is configured; match the surrounding code.

## Testing

Tests live in `tests/test_*.py` with helpers in `tests/support.py`; add new ones there using `unittest` and Flask's test client. Database tests subclass `DatabaseTestCase`, which applies `migrations/` to the database at `DATABASE_URL` and starts each test from `create_app(reset_on_start=True)` with an empty `payments` table; `unreachable_database()` simulates an outage. There is one module per layer: `test_card.py` (domain `Card`), `test_result.py`, `test_database.py` (`Postgres`, migrations, startup failures), `test_unit_of_work.py` (UnitOfWork and Services), `test_payments_repository.py` (repository and `Payment` model), `test_payments_api.py` (ledger endpoints, auth, concurrency), `test_pay_booking.py` (temporary stateless route), `test_health.py`, `test_app.py` and `test_logger.py`. Database tests get the service token set; send `AUTH` as headers. Cover every new endpoint's success and error paths, including idempotent retries and log levels.

## Security and configuration

- Never persist full card numbers or CVCs; store only the last four digits. Never log card data or database exception text.
- Treat the repo as public (the sibling repos are): no `.env`, credentials or tokens in commits.
- Variables: `DATABASE_URL`, `APP_REVISION` (reported by `/health`), `LOG_LEVEL`, `RESET_DB_ON_START`, `SERVICE_TOKEN` (shared secret; unset means every payment endpoint answers `401`).
- `RESET_DB_ON_START=true` truncates the `payments` table. Use it only against disposable local or test data, never in a deployment.

## Workflow

Follow `spec/docs/process/CONTRIBUTING.md`: branch per change, pull request with what/why/how-checked, review before merge, no direct pushes to `main`. Commit subjects are short and descriptive. In PRs, list the validation commands you ran and include request/response examples for endpoint changes.

## Maintaining this file

Keep this file about how to work in this repo. Behaviour belongs in the spec. If the layout changes (new modules, Dockerfile, migrations, CI), update the sections above in the same PR.
