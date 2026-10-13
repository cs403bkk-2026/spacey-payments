"""PaymentsRepository (src/repositories/payments.py) and the Payment model
mapping onto the migrated payments table."""

from unittest import mock

from sqlalchemy.exc import IntegrityError, OperationalError

from src.models.payment import Payment, PaymentCurrency, PaymentStatus
from src.repositories.payments import PaymentsRepository
from src.unit_of_work import UnitOfWork
from tests.support import DatabaseTestCase


class TruncateTests(DatabaseTestCase):
    def test_truncate_empties_the_table_and_restarts_ids(self):
        self.insert_payment(booking_id=1)
        self.insert_payment(booking_id=2)

        with UnitOfWork().transaction() as services:
            result = services.payments.repository.truncate()

        self.assertTrue(result.successful)
        self.assertEqual(self.count_payments(), 0)
        self.assertEqual(self.insert_payment().id, 1)

    def test_truncate_reports_database_errors_as_a_failure(self):
        session = mock.Mock()
        session.execute.side_effect = OperationalError("TRUNCATE", {}, Exception("down"))

        result = PaymentsRepository(session).truncate()

        self.assertTrue(result.failed)
        self.assertIn("down", result.reason)


class PaymentModelTests(DatabaseTestCase):
    def test_round_trips_with_defaults(self):
        created = self.insert_payment(booking_id=7, amount_cents=2500)

        with UnitOfWork().transaction() as services:
            payment = services.session.get(Payment, created.id)

        self.assertEqual(payment.booking_id, 7)
        self.assertEqual(payment.amount_cents, 2500)
        self.assertEqual(payment.currency, PaymentCurrency.USD)
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(payment.card_last4, "4242")
        self.assertIsNotNone(payment.created_at)

    def test_every_status_is_accepted_by_the_database(self):
        for status in PaymentStatus:
            with self.subTest(status=status):
                self.assertEqual(self.insert_payment(status=status).status, status)

    def test_amount_must_be_positive(self):
        for amount in (0, -100):
            with self.subTest(amount=amount):
                with self.assertRaises(IntegrityError):
                    self.insert_payment(amount_cents=amount)
        self.assertEqual(self.count_payments(), 0)

    def test_repr_has_no_card_data(self):
        self.assertNotIn("4242", repr(self.insert_payment()))
