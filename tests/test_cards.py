import unittest

from src.domain.card import Card


class ValidateCardTests(unittest.TestCase):
    def test_valid_card_has_no_error(self):
        self.assertIsNone(Card("4242424242424242", "123", "12/99").validate())

    def test_bad_fields_give_a_specific_error(self):
        cases = [
            (("123", "12/99", "123"), "card_number must be 13-19 digits"),
            (("4242424242424242", "12/99", "1"), "cvc must be 3 or 4 digits"),
            (("4242424242424242", "13/30", "123"), "expiry must be in MM/YY format"),
            (("4242424242424242", "bad", "123"), "expiry must be in MM/YY format"),
            (("4242424242424242", "01/20", "123"), "card has expired"),
        ]
        for args, message in cases:
            with self.subTest(args=args):
                self.assertEqual(Card(args[0], args[2], args[1]).validate(), message)
