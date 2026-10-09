from tests.support import VALID_CARD, AppTestCase


class PayBookingTests(AppTestCase):
    def pay(self, booking_id, **body):
        return self.client.post(f"/bookings/{booking_id}/pay", json=body)

    def test_valid_card_marks_booking_paid_and_stores_last4_only(self):
        booking_id = self.add_booking()
        resp = self.pay(booking_id, **VALID_CARD)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["paid"])
        self.assertEqual(body["card_last4"], "4242")
        self.assertNotIn("card_number", body)

    def test_missing_booking_is_404(self):
        resp = self.pay(999, **VALID_CARD)
        self.assertEqual(resp.status_code, 404)

    def test_invalid_card_fields_are_400_and_leave_booking_unpaid(self):
        booking_id = self.add_booking()
        bad = [
            {**VALID_CARD, "card_number": "123"},
            {**VALID_CARD, "cvc": "1"},
            {**VALID_CARD, "expiry": "13/30"},
            {**VALID_CARD, "expiry": "01/20"},
            {},
        ]
        for body in bad:
            with self.subTest(body=body):
                self.assertEqual(self.pay(booking_id, **body).status_code, 400)
        with self.app.db.cursor() as cur:
            cur.execute("SELECT paid FROM bookings WHERE id = %s", (booking_id,))
            self.assertFalse(cur.fetchone()["paid"])

    def test_forced_failure_is_402_and_leaves_booking_unpaid(self):
        booking_id = self.add_booking()
        resp = self.pay(booking_id, force_failure=True, **VALID_CARD)
        self.assertEqual(resp.status_code, 402)
        with self.app.db.cursor() as cur:
            cur.execute("SELECT paid FROM bookings WHERE id = %s", (booking_id,))
            self.assertFalse(cur.fetchone()["paid"])

    def test_paying_twice_is_idempotent_and_needs_no_card(self):
        booking_id = self.add_booking()
        self.pay(booking_id, **VALID_CARD)
        second = self.pay(booking_id)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["card_last4"], "4242")


class PayLoggingTests(AppTestCase):
    def pay(self, booking_id, **body):
        return self.client.post(f"/bookings/{booking_id}/pay", json=body)

    def test_each_outcome_is_logged_at_its_level_without_card_data(self):
        booking_id = self.add_booking()
        with self.assertLogs("spacey_payments", level="DEBUG") as logs:
            self.pay(999, **VALID_CARD)
            self.pay(booking_id, **{**VALID_CARD, "cvc": "1"})
            self.pay(booking_id, force_failure=True, **VALID_CARD)
            self.pay(booking_id, **VALID_CARD)
            self.pay(booking_id, **VALID_CARD)
        lines = [f"{r.levelname} {r.getMessage()}" for r in logs.records]
        for expected in (
            f"DEBUG payment booking_id={booking_id} outcome=started",
            "WARNING payment booking_id=999 outcome=not_found",
            f"WARNING payment booking_id={booking_id} outcome=invalid_card",
            f"WARNING payment booking_id={booking_id} outcome=failed",
            f"INFO payment booking_id={booking_id} outcome=succeeded",
            f"INFO payment booking_id={booking_id} outcome=already_paid",
        ):
            self.assertIn(expected, lines)
        self.assertNotIn("4242424242424242", " ".join(lines))

    def test_database_failure_is_logged_as_error_and_returns_500(self):
        booking_id = self.add_booking()
        self.app.db.close()
        with self.assertLogs("spacey_payments", level="ERROR") as logs:
            resp = self.pay(booking_id, **VALID_CARD)
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(
            [r.getMessage() for r in logs.records],
            [f"payment booking_id={booking_id} outcome=database_error"],
        )
