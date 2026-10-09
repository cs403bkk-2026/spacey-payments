"""Database access for payments. SQL only - no validation or HTTP here."""

BOOKING_COLUMNS = "id, member, paid, amount_cents, card_last4"


def reset_tables(db) -> None:
    """Wipe all rows and restart ids. Only used for tests and an opt-in
    local reset (RESET_DB_ON_START=true)."""
    with db.cursor() as cur:
        cur.execute("TRUNCATE bookings RESTART IDENTITY CASCADE")


def get_booking(db, booking_id):
    with db.cursor() as cur:
        cur.execute(
            f"SELECT {BOOKING_COLUMNS} FROM bookings WHERE id = %s",
            (booking_id,),
        )
        return cur.fetchone()


def mark_paid(db, booking_id, card_last4):
    """Set the booking paid and store the card's last 4 digits."""
    with db.cursor() as cur:
        cur.execute(
            "UPDATE bookings SET paid = TRUE, card_last4 = %s WHERE id = %s "
            f"RETURNING {BOOKING_COLUMNS}",
            (card_last4, booking_id),
        )
        return cur.fetchone()
