"""Card validation (src/domain/card.py). Boundary cases are ported from the
spacey monolith's PT-005 tests; card numbers that are meant to be accepted pass
the Luhn check, so only the rule under test decides."""

import unittest

from src.domain.card import Card
from tests.support import VALID_CARD, expiry_months_from_now


def card(**overrides) -> Card:
    return Card(**{"number": VALID_CARD["card_number"], "cvc": VALID_CARD["cvc"],
                   "expiry": VALID_CARD["expiry"], **overrides})


class FromBodyTests(unittest.TestCase):
    def test_builds_a_card_from_a_request_body(self):
        result = Card.from_body(VALID_CARD)
        self.assertTrue(result.successful)
        self.assertEqual(result.value, Card("4242424242424242", "123", "12/99"))

    def test_extra_fields_are_ignored(self):
        body = {**VALID_CARD, "force_failure": True, "booking_id": 7}
        self.assertEqual(Card.from_body(body).value, Card.from_body(VALID_CARD).value)

    def test_missing_field_gets_that_fields_error(self):
        expected = {"card_number": "card_number must be 13-19 digits",
                    "cvc": "cvc must be 3 or 4 digits",
                    "expiry": "expiry must be in MM/YY format"}
        for missing, message in expected.items():
            with self.subTest(missing=missing):
                body = {k: v for k, v in VALID_CARD.items() if k != missing}
                self.assertEqual(Card.from_body(body).reason, message)

    def test_non_string_fields_are_rejected_like_bad_formats(self):
        cases = [
            ("card_number", 4242424242424242, "card_number must be 13-19 digits"),
            ("card_number", ["4242424242424242"], "card_number must be 13-19 digits"),
            ("card_number", None, "card_number must be 13-19 digits"),
            ("cvc", 123, "cvc must be 3 or 4 digits"),
            ("cvc", None, "cvc must be 3 or 4 digits"),
            ("expiry", 1230, "expiry must be in MM/YY format"),
            ("expiry", None, "expiry must be in MM/YY format"),
        ]
        for field, value, message in cases:
            with self.subTest(field=field, value=value):
                self.assertEqual(Card.from_body({**VALID_CARD, field: value}).reason, message)

    def test_empty_body_gets_the_card_number_error(self):
        self.assertEqual(Card.from_body({}).reason, "card_number must be 13-19 digits")


class Last4Tests(unittest.TestCase):
    def test_last4_is_the_final_four_digits(self):
        for number in ("4111111111111111", "378282246310005",
                       "4222222222222", "6011000000000000001"):
            with self.subTest(number=number):
                self.assertEqual(card(number=number).last4, number[-4:])


class ValidateTests(unittest.TestCase):
    def test_valid_card_has_no_error(self):
        self.assertIsNone(card().validate())

    def test_card_number_length_and_format_boundaries(self):
        cases = [
            ("424242424242", False),          # 12 digits, one too short
            ("4222222222222", True),          # 13 digits, shortest allowed
            ("6011000000000000001", True),    # 19 digits, longest allowed
            ("42424242424242424242", False),  # 20 digits, one too long
            ("4242 4242 4242 4242", False),   # spaces are not accepted
            ("4242-4242-4242-4242", False),   # dashes are not accepted
            ("4242abcd42424242", False),
            ("", False),
        ]
        for number, accepted in cases:
            with self.subTest(number=number):
                expected = None if accepted else "card_number must be 13-19 digits"
                self.assertEqual(card(number=number).validate(), expected)

    def test_card_failing_the_luhn_check_is_rejected(self):
        # 4242424242424242 is valid; changing the last digit breaks the checksum
        self.assertEqual(card(number="4242424242424241").validate(),
                         "card_number is not a valid card number")

    def test_cvc_boundaries(self):
        cases = [("12", False), ("123", True), ("1234", True), ("12345", False),
                 ("", False), (" 123", False), ("abc", False)]
        for cvc, accepted in cases:
            with self.subTest(cvc=cvc):
                expected = None if accepted else "cvc must be 3 or 4 digits"
                self.assertEqual(card(cvc=cvc).validate(), expected)

    def test_malformed_expiry_is_a_format_error(self):
        for expiry in ("00/30", "13/30", "1/30", "12/2030", "12-30", "1230",
                       "12/3", "", " 12/30", "2030-12"):
            with self.subTest(expiry=expiry):
                self.assertEqual(card(expiry=expiry).validate(),
                                 "expiry must be in MM/YY format")

    def test_expiry_month_boundary(self):
        cases = [(-1, False), (0, True), (1, True)]  # last, this and next month
        for months, accepted in cases:
            with self.subTest(months_from_now=months):
                expected = None if accepted else "card has expired"
                self.assertEqual(card(expiry=expiry_months_from_now(months)).validate(),
                                 expected)

    def test_the_first_failing_field_decides_the_error(self):
        all_bad = {"number": "42", "cvc": "1", "expiry": "99/99"}
        self.assertEqual(card(**all_bad).validate(),
                         "card_number must be 13-19 digits")
        self.assertEqual(card(**{**all_bad, "number": "4242424242424242"}).validate(),
                         "cvc must be 3 or 4 digits")
        self.assertEqual(
            card(**{**all_bad, "number": "4242424242424242", "cvc": "123"}).validate(),
            "expiry must be in MM/YY format",
        )
