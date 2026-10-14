"""The temporary, stateless POST /payment/bookings/<id>/pay (PT-022), ported
from spacey PR #244's tests/test_payment_api.py and test_payment_logging.py."""

import logging

from tests.support import AUTH, VALID_CARD, DatabaseTestCase, unreachable_database


class PayBookingTests(DatabaseTestCase):
    def pay(self, booking_id=7, **kwargs):
        return self.client.post(f"/payment/bookings/{booking_id}/pay", headers=AUTH, **kwargs)

    def test_valid_card_returns_only_the_outcome(self):
        resp = self.pay(json={**VALID_CARD, "card_number": "4111111111111111"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(),
                         {"booking_id": 7, "status": "success", "card_last4": "1111"})

    def test_records_nothing(self):
        self.pay(json=VALID_CARD)
        self.pay(json={**VALID_CARD, "force_failure": True})
        self.assertEqual(self.count_payments(), 0)

    def test_does_not_need_the_database(self):
        with unreachable_database():
            self.assertEqual(self.pay(json=VALID_CARD).status_code, 200)

    def test_invalid_card_is_400_with_the_first_problem(self):
        cases = [
            ({**VALID_CARD, "card_number": "4242"}, "card_number must be 13-19 digits"),
            ({**VALID_CARD, "card_number": "4242424242424241"},
             "card_number is not a valid card number"),
            ({**VALID_CARD, "cvc": "12"}, "cvc must be 3 or 4 digits"),
            ({**VALID_CARD, "expiry": "13/30"}, "expiry must be in MM/YY format"),
            ({**VALID_CARD, "expiry": "01/20"}, "card has expired"),
            ({"card_number": "4111111111111111"}, "cvc must be 3 or 4 digits"),
            ({"card_number": "4111111111111111", "cvc": "123"},
             "expiry must be in MM/YY format"),
            ({"card_number": "42", "cvc": "1", "expiry": "99/99"},
             "card_number must be 13-19 digits"),
        ]
        for body, message in cases:
            with self.subTest(body=body):
                resp = self.pay(json=body)
                self.assertEqual((resp.status_code, resp.get_json()), (400, {"error": message}))

    def test_force_failure_is_402(self):
        resp = self.pay(json={**VALID_CARD, "force_failure": True})
        self.assertEqual((resp.status_code, resp.get_json()), (402, {"error": "payment failed"}))

    def test_only_a_literal_true_forces_failure(self):
        for value in ("true", 1, False, None):
            with self.subTest(force_failure=value):
                self.assertEqual(self.pay(json={**VALID_CARD, "force_failure": value})
                                 .status_code, 200)

    def test_invalid_card_wins_over_force_failure(self):
        resp = self.pay(json={**VALID_CARD, "cvc": "1", "force_failure": True})
        self.assertEqual(resp.status_code, 400)

    def test_trailing_newlines_and_non_ascii_digits_are_rejected(self):
        errors = {
            "card_number": "card_number must be 13-19 digits",
            "cvc": "cvc must be 3 or 4 digits",
            "expiry": "expiry must be in MM/YY format",
        }
        for field, error in errors.items():
            value = VALID_CARD[field]
            for bad in (value + "\n", value.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))):
                with self.subTest(field=field, value=bad):
                    resp = self.pay(json={**VALID_CARD, field: bad})
                    self.assertEqual((resp.status_code, resp.get_json()), (400, {"error": error}))

    def test_non_object_or_malformed_body_is_read_as_empty(self):
        for data in ("null", "[]", '"card"', "42", "true", "{not json", ""):
            with self.subTest(data=data):
                resp = self.pay(data=data, content_type="application/json")
                self.assertEqual((resp.status_code, resp.get_json()),
                                 (400, {"error": "card_number must be 13-19 digits"}))

    def test_booking_id_must_be_a_positive_integer_path(self):
        for booking_id in ("0", "abc", "-1", "2147483648"):
            with self.subTest(booking_id=booking_id):
                self.assertEqual(self.pay(booking_id=booking_id, json=VALID_CARD).status_code,
                                 404)

    def test_logs_each_outcome_without_card_data(self):
        cases = [
            ({**VALID_CARD}, logging.INFO, "succeeded"),
            ({**VALID_CARD, "force_failure": True}, logging.WARNING, "failed"),
            ({**VALID_CARD, "card_number": "sensitive-invalid-card"},
             logging.WARNING, "invalid_card"),
        ]
        for body, level, outcome in cases:
            with self.subTest(outcome=outcome):
                with self.assertLogs("spacey_payments", level="DEBUG") as logs:
                    self.pay(json=body)
                self.assertEqual(
                    [(r.levelno, r.getMessage()) for r in logs.records],
                    [(logging.DEBUG, "payment booking_id=7 outcome=started"),
                     (level, f"payment booking_id=7 outcome={outcome}")])
                output = "\n".join(logs.output)
                for value in (*VALID_CARD.values(), "4242", "sensitive-invalid-card"):
                    self.assertNotIn(value, output)
