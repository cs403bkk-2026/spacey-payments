import os
import re
from datetime import datetime, timezone

import psycopg
from flask import Flask, jsonify, request
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://spacey:spacey@localhost:5432/spacey"
)


def get_connection(database_url: str) -> psycopg.Connection:
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=True)
    except psycopg.OperationalError as error:
        raise SystemExit(
            f"Could not connect to the database at DATABASE_URL={database_url!r}\n"
            f"{error}\n"
            "Is Postgres running? Try: docker compose up db -d"
        ) from None
    with conn.cursor() as cur:
        # Only the payment-related columns of the old bookings table.
        # No foreign keys: spaces and users now live in other services.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                member TEXT NOT NULL,
                paid BOOLEAN NOT NULL,
                amount_cents INTEGER,
                card_last4 TEXT
            )
            """
        )
        # Mocked subscriptions, keyed by the trimmed lower-case member name.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                member TEXT PRIMARY KEY,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                started_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    return conn


CARD_NUMBER_RE = re.compile(r"^\d{13,19}$")
CVC_RE = re.compile(r"^\d{3,4}$")
EXPIRY_RE = re.compile(r"^(0[1-9]|1[0-2])/(\d{2})$")


def validate_card(card_number, expiry, cvc) -> str | None:
    """Returns an error message, or None if the (mocked) card looks valid -
    right shape and not expired, not a real Luhn/network check."""
    if not isinstance(card_number, str) or not CARD_NUMBER_RE.match(card_number):
        return "card_number must be 13-19 digits"
    if not isinstance(cvc, str) or not CVC_RE.match(cvc):
        return "cvc must be 3 or 4 digits"
    if not isinstance(expiry, str):
        return "expiry must be in MM/YY format"
    match = EXPIRY_RE.match(expiry)
    if match is None:
        return "expiry must be in MM/YY format"
    month, year = int(match.group(1)), 2000 + int(match.group(2))
    now = datetime.now(timezone.utc)
    if (year, month) < (now.year, now.month):
        return "card has expired"
    return None


def member_key(name: str) -> str:
    return name.strip().lower()


def is_subscribed(cur, member) -> bool:
    if not isinstance(member, str):
        return False
    cur.execute(
        "SELECT 1 FROM subscriptions WHERE member = %s AND active",
        (member_key(member),),
    )
    return cur.fetchone() is not None


def reset_tables(conn: psycopg.Connection) -> None:
    """Wipe all rows and restart ids. Only used for tests and an opt-in
    local reset (RESET_DB_ON_START=true)."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE bookings, subscriptions RESTART IDENTITY CASCADE")


def create_app(
        database_url: str = DATABASE_URL, reset_on_start: bool | None = None
) -> Flask:
    if reset_on_start is None:
        reset_on_start = os.getenv("RESET_DB_ON_START", "false").lower() == "true"

    app = Flask(__name__)
    app.db = get_connection(database_url)
    if reset_on_start:
        reset_tables(app.db)

    @app.get("/health")
    def health():
        try:
            with app.db.cursor() as cur:
                cur.execute("SELECT 1")
        except psycopg.Error:
            return jsonify(status="error", error="database unreachable"), 503

        return jsonify(
            status="ok",
            revision=os.getenv("APP_REVISION", "local"),
        )

    def mark_booking_paid(booking_id, card_number, expiry, cvc, force_failure=False):
        """Mocked payment: no provider, so it succeeds unless force_failure
        is set or the card doesn't look valid (see validate_card). Paying an
        already-paid booking is a no-op rather than an error, so a retried
        request can't break the flow or charge twice - and doesn't need a
        card either. Only the card's last 4 digits are ever stored.
        Returns (payload, status) - the booking, or an {"error": ...}."""
        with app.db.cursor() as cur:
            cur.execute(
                "SELECT id, member, paid, amount_cents, card_last4 "
                "FROM bookings WHERE id = %s",
                (booking_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"error": "booking not found"}, 404

            if row["paid"]:
                return row, 200

            card_error = validate_card(card_number, expiry, cvc)
            if card_error:
                return {"error": card_error}, 400

            if force_failure:
                return {"error": "payment failed"}, 402

            cur.execute(
                "UPDATE bookings SET paid = TRUE, card_last4 = %s WHERE id = %s "
                "RETURNING id, member, paid, amount_cents, card_last4",
                (card_number[-4:], booking_id),
            )
            row = cur.fetchone()

        return row, 200

    @app.post("/bookings/<int:booking_id>/pay")
    def pay_booking(booking_id):
        body = request.get_json(silent=True) or {}
        payload, status = mark_booking_paid(
            booking_id,
            body.get("card_number"),
            body.get("expiry"),
            body.get("cvc"),
            force_failure=body.get("force_failure") is True,
        )
        return jsonify(payload), status

    @app.post("/members/<name>/subscribe")
    def subscribe_member(name):
        # Mocked, like payment: no provider, always succeeds. Subscribing
        # again is a no-op, so a retried request can't break anything.
        member = member_key(name)
        if not member:
            return jsonify(error="member name must not be blank"), 400

        with app.db.cursor() as cur:
            cur.execute(
                "INSERT INTO subscriptions (member) VALUES (%s) "
                "ON CONFLICT (member) DO UPDATE SET active = TRUE "
                "RETURNING member, active, started_at",
                (member,),
            )
            row = cur.fetchone()

        return jsonify(
            member=row["member"],
            active=row["active"],
            started_at=row["started_at"].astimezone(timezone.utc).isoformat(),
        )

    return app


app = create_app()
