from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import Select, TextClause, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from src.models.payment import Payment, PaymentCurrency, PaymentStatus
from src.repositories.repository import Repository
from src.result import Result

TRUNCATE_PAYMENTS: TextClause = text(
    "TRUNCATE payments RESTART IDENTITY CASCADE"
)


@dataclass(slots=True, frozen=True)
class PaymentsRepository(Repository):
    """SQL for the payments ledger. Every method returns a failed Result instead
    of raising on a database error, after rolling the session back; the reason
    is database text, so callers must never log or return it."""

    def _run[T](self, query: Callable[[], T]) -> Result[T]:
        try:
            return Result.success(query())

        except SQLAlchemyError as err:
            self._session.rollback()
            return Result.failure(f"{str(err)}")

    def truncate(self) -> Result[None]:
        def query() -> None:
            self._session.execute(TRUNCATE_PAYMENTS)

        return self._run(query)

    def get(self, payment_id: int) -> Result[Optional[Payment]]:
        return self._run(lambda: self._session.get(Payment, payment_id))

    def get_by_idempotency_key(self, key: str) -> Result[Optional[Payment]]:
        query: Select = select(Payment).where(Payment.idempotency_key == key)
        return self._run(lambda: self._session.scalars(query).first())

    def get_success_for_booking(self, booking_id: int) -> Result[Optional[Payment]]:
        query: Select = select(Payment).where(
            Payment.booking_id == booking_id,
            Payment.status == PaymentStatus.SUCCESS,
        )
        return self._run(lambda: self._session.scalars(query).first())

    def list_for_booking(self, booking_id: int) -> Result[list[Payment]]:
        query: Select = (
            select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.id)
        )
        return self._run(lambda: list(self._session.scalars(query)))

    def insert(self, booking_id: int, amount_cents: int, status: PaymentStatus,
               idempotency_key: str, card_last4: Optional[str],
               reason: Optional[str] = None,
               currency: PaymentCurrency = PaymentCurrency.USD) -> Result[Optional[Payment]]:
        """Records one payment and returns it, or None if a unique index already
        holds a row for this idempotency key or a success for this booking (a
        concurrent request won). Only the card's last four digits are accepted."""
        statement = (
            insert(Payment)
            .values(booking_id=booking_id, amount_cents=amount_cents,
                    currency=currency, status=status, reason=reason,
                    card_last4=card_last4, idempotency_key=idempotency_key)
            .on_conflict_do_nothing()
            .returning(Payment)
        )
        return self._run(lambda: self._session.scalars(statement).first())
