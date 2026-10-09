"""Database connection and migrations."""

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from src.logger import logger

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def get_connection(database_url: str) -> psycopg.Connection:
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=True)
    except psycopg.OperationalError as error:
        logger.error("startup outcome=database_unreachable")
        raise SystemExit(
            "Could not connect to the database (check DATABASE_URL).\n"
            f"{error}\n"
            "Is Postgres running? Try: docker compose up db -d"
        ) from None
    run_migrations(conn)
    return conn


def run_migrations(conn: psycopg.Connection) -> None:
    """Apply migrations/*.sql in filename order, once each. Migrations should
    also be safe to re-run (IF NOT EXISTS and similar)."""
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cur.execute("SELECT name FROM schema_migrations")
        applied = {row["name"] for row in cur.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            cur.execute(path.read_text())
            cur.execute(
                "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
            )
            logger.info("migration applied name=%s", path.name)
