"""Shared test helpers. Tests need PostgreSQL at DATABASE_URL and wipe its
payments table, so point it at a disposable database."""

import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional
from unittest import mock

from sqlalchemy import func, select

from src import config
from src.app import create_app
from src.database import Postgres
from src.models.payment import Payment, PaymentStatus
from src.unit_of_work import UnitOfWork

# A mocked, obviously-fake card - always valid, never a real payment.
VALID_CARD: dict[str, str] = {
    "card_number": "4242424242424242",
    "expiry": "12/99",
    "cvc": "123",
}

UNREACHABLE_DATABASE_URL: str = "postgresql://example:private-password@127.0.0.1:1/payments"

SERVICE_TOKEN: str = "test-service-token"
AUTH: dict[str, str] = {"X-Service-Token": SERVICE_TOKEN}


def expiry_months_from_now(months: int) -> str:
    """MM/YY for the given number of months from the current UTC month."""
    now = datetime.now(timezone.utc)
    index = now.year * 12 + (now.month - 1) + months
    return f"{index % 12 + 1:02d}/{(index // 12) % 100:02d}"


@contextmanager
def unreachable_database() -> Iterator[None]:
    """Points Postgres at a closed port for the duration of the block."""
    healthy = Postgres.get()
    with mock.patch.dict(os.environ, {Postgres.URL_KEY: UNREACHABLE_DATABASE_URL}):
        Postgres.init()
    try:
        yield
    finally:
        Postgres.get().close()
        Postgres._instance = healthy


class DatabaseTestCase(unittest.TestCase):
    """Starts each test with a migrated, empty payments table and the service
    token set; send AUTH as headers to reach the payment endpoints."""

    def setUp(self):
        token = mock.patch.object(config, "SERVICE_TOKEN", SERVICE_TOKEN)
        token.start()
        self.addCleanup(token.stop)
        self.app = create_app(reset_on_start=True)
        self.client = self.app.test_client()
        self.addCleanup(lambda: Postgres.get().close())

    def insert_payment(self, booking_id: int = 1, amount_cents: int = 1500,
                       status: PaymentStatus = PaymentStatus.SUCCESS,
                       idempotency_key: Optional[str] = None) -> Payment:
        """Seeds a row directly, bypassing the API."""
        with UnitOfWork().transaction() as services:
            payment = Payment(booking_id=booking_id, amount_cents=amount_cents,
                              status=status, card_last4="4242",
                              idempotency_key=idempotency_key)
            services.session.add(payment)
            services.session.flush()
            return payment

    def count_payments(self) -> int:
        with UnitOfWork().transaction() as services:
            return services.session.scalar(select(func.count()).select_from(Payment))

    def all_payments(self) -> list[Payment]:
        with UnitOfWork().transaction() as services:
            return list(services.session.scalars(select(Payment).order_by(Payment.id)))
