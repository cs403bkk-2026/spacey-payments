import unittest

from src.result import Result


class ResultTests(unittest.TestCase):
    def test_success_carries_a_value(self):
        result = Result.success(42)
        self.assertTrue(result.successful)
        self.assertFalse(result.failed)
        self.assertEqual(result.value, 42)
        self.assertEqual(result.reason, "")

    def test_success_without_a_value_is_none(self):
        self.assertIsNone(Result.success().value)

    def test_failure_carries_a_reason(self):
        result = Result.failure("database unreachable")
        self.assertTrue(result.failed)
        self.assertFalse(result.successful)
        self.assertEqual(result.reason, "database unreachable")

    def test_reading_the_value_of_a_failure_raises(self):
        with self.assertRaises(AssertionError) as error:
            Result.failure("nope").value
        self.assertIn("nope", str(error.exception))

    def test_results_are_immutable(self):
        with self.assertRaises(AttributeError):
            setattr(Result.success(1), "reason", "changed")
