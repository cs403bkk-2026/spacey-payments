"""Shared test helpers. Tests need PostgreSQL at DATABASE_URL and wipe its
bookings table, so point it at a disposable database."""

import unittest

from src.app import create_app

VALID_CARD = {"card_number": "4242424242424242", "expiry": "12/99", "cvc": "123"}


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(reset_on_start=True)
        self.client = self.app.test_client()
        self.addCleanup(self.app.db.close)

    def add_booking(self, member="annabel", amount_cents=1500, paid=False):
        with self.app.db.cursor() as cur:
            cur.execute(
                "INSERT INTO bookings (member, paid, amount_cents) "
                "VALUES (%s, %s, %s) RETURNING id",
                (member, paid, amount_cents),
            )
            return cur.fetchone()["id"]
