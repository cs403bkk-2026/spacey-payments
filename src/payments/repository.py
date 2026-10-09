"""Database access for payments. SQL only - no validation or HTTP here."""

PAYMENT_COLUMNS = (
    "id, booking_id, amount_cents, currency, status, reason, "
    "card_last4, idempotency_key, created_at"
)


def get_payment(db, payment_id):
    with db.cursor() as cur:
        cur.execute(
            f"SELECT {PAYMENT_COLUMNS} FROM payments WHERE id = %s",
            (payment_id,),
        )
        return cur.fetchone()


def get_refund_for_payment(db, payment_id):
    with db.cursor() as cur:
        cur.execute(
            f"SELECT {PAYMENT_COLUMNS} FROM payments WHERE idempotency_key = %s",
            (f"refund:{payment_id}",),
        )
        return cur.fetchone()


def insert_refund(db, payment, reason):
    """Return (refund, created); the unique key arbitrates concurrent retries."""
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO payments (booking_id, amount_cents, currency, status, "
            "reason, card_last4, idempotency_key) "
            "VALUES (%s, %s, %s, 'refunded', %s, %s, %s) "
            "ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL "
            f"DO NOTHING RETURNING {PAYMENT_COLUMNS}",
            (payment["booking_id"], payment["amount_cents"], payment["currency"],
             reason, payment["card_last4"], f"refund:{payment['id']}"),
        )
        row = cur.fetchone()
    if row is not None:
        return row, True
    return get_refund_for_payment(db, payment["id"]), False


def reset_tables(db) -> None:
    """Wipe all rows and restart ids. Only used for tests and an opt-in
    local reset (RESET_DB_ON_START=true)."""
    with db.cursor() as cur:
        cur.execute("TRUNCATE payments RESTART IDENTITY CASCADE")
