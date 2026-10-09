import unittest

from src.payments.models.cards import validate_card


class ValidateCardTests(unittest.TestCase):
    def test_valid_card_has_no_error(self):
        self.assertIsNone(validate_card("4242424242424242", "12/99", "123"))

    def test_bad_fields_give_a_specific_error(self):
        cases = [
            (("123", "12/99", "123"), "card_number must be 13-19 digits"),
            (("4242424242424242", "12/99", "1"), "cvc must be 3 or 4 digits"),
            (("4242424242424242", "13/30", "123"), "expiry must be in MM/YY format"),
            (("4242424242424242", None, "123"), "expiry must be in MM/YY format"),
            (("4242424242424242", "01/20", "123"), "card has expired"),
        ]
        for args, message in cases:
            with self.subTest(args=args):
                self.assertEqual(validate_card(*args), message)
