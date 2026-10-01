# Repository Guidelines

## Project Structure & Module Organization

`src/payment_functionality.py` contains the Flask application, PostgreSQL table initialization, card validation, booking payment endpoint, and member subscription endpoint. Payments and subscriptions are mocked; no payment provider is integrated. There are currently no test, asset, or migration directories, dependency manifest, or build configuration. Keep related changes in the existing module unless separation solves a concrete need.

## Build, Test, and Development Commands

Use Python 3.10 or newer and a running PostgreSQL instance.

- `python3 -m venv .venv` and `source .venv/bin/activate`: create and activate a local environment.
- `python -m pip install Flask "psycopg[binary]"`: install the libraries imported by the application.
- `export DATABASE_URL='postgresql://spacey:spacey@localhost:5432/spacey'`: configure a local database; provision the database and role separately.
- `python -m flask --app src.payment_functionality run --debug`: start the local development server. Importing the module connects to PostgreSQL and creates missing tables.
- `curl http://127.0.0.1:5000/health`: check application and database connectivity.

No build step or Docker Compose file is checked in.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions and variables, and uppercase constants. Follow the existing type hints and short docstrings. Keep SQL parameterized with `%s` placeholders and separate parameters. Represent monetary values as integer cents. No formatter or linter is configured.

## Testing Guidelines

No test framework, suite, or coverage threshold is configured. Add focused regression tests under `tests/test_*.py`; Python's `unittest` and Flask's test client are sufficient. Run them with `python -m unittest discover -s tests` once tests exist. Use a dedicated PostgreSQL test database. Cover invalid cards, missing bookings, forced payment failures, repeated payments, and normalized subscription names.

## Commit & Pull Request Guidelines

The current history contains `added payment functionality`; no formal convention is established. Use short, descriptive commit subjects. In pull requests, explain behavior changes, link relevant issues, and report validation commands and results. Include request/response examples for endpoint changes.

## Security & Configuration

Keep credentials out of commits and logs. Never persist full card numbers or CVCs; store only the last four digits. `RESET_DB_ON_START=true` truncates both tables: enable it only against disposable local or test data.
