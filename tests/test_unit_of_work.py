"""UnitOfWork (src/unit_of_work.py) and Services (src/services/services.py)."""

from typing import cast

from sqlalchemy.orm import Session

from src.models.payment import Payment, PaymentStatus
from src.services.health import HealthService
from src.services.payment import PaymentService
from src.services.services import InvalidSessionError, Services
from src.unit_of_work import NestedTransactionError, UnitOfWork
from tests.support import DatabaseTestCase


class UnitOfWorkTests(DatabaseTestCase):
    def test_changes_are_committed_when_the_block_succeeds(self):
        self.insert_payment()
        self.assertEqual(self.count_payments(), 1)

    def test_changes_are_rolled_back_and_the_error_reraised(self):
        with self.assertRaises(ValueError):
            with UnitOfWork().transaction() as services:
                services.session.add(Payment(booking_id=1, amount_cents=1500,
                                             status=PaymentStatus.SUCCESS))
                services.session.flush()
                raise ValueError("boom")
        self.assertEqual(self.count_payments(), 0)

    def test_nested_transactions_are_rejected(self):
        uow = UnitOfWork()
        with uow.transaction():
            with self.assertRaises(NestedTransactionError):
                with uow.transaction():
                    pass

    def test_unit_of_work_is_reusable_after_a_block(self):
        uow = UnitOfWork()
        with self.assertRaises(ValueError):
            with uow.transaction():
                raise ValueError("boom")
        with uow.transaction() as services:
            self.assertTrue(services.health.check().successful)

    def test_services_are_invalidated_after_the_block(self):
        with UnitOfWork().transaction() as services:
            pass
        with self.assertRaises(InvalidSessionError):
            services.session
        with self.assertRaises(InvalidSessionError):
            services.payments


class ServicesTests(DatabaseTestCase):
    def test_services_are_created_lazily_and_reused(self):
        with UnitOfWork().transaction() as services:
            self.assertIsInstance(services.payments, PaymentService)
            self.assertIsInstance(services.health, HealthService)
            self.assertIs(services.payments, services.payments)
            self.assertIs(services.health, services.health)
            self.assertIs(services.payments.repository, services.payments.repository)

    def test_invalidate_drops_the_session_and_services(self):
        services = Services(cast(Session, object()))
        services.payments
        services.invalidate()
        with self.assertRaises(InvalidSessionError):
            services.health
