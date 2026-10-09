"""Database access for payments. SQL only - no validation or HTTP here."""


def reset_tables(db) -> None:
    """Wipe all rows and restart ids. Only used for tests and an opt-in
    local reset (RESET_DB_ON_START=true)."""
    with db.cursor() as cur:
        cur.execute("TRUNCATE payments RESTART IDENTITY CASCADE")
