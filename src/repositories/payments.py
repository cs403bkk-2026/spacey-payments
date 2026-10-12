from dataclasses import dataclass

from sqlalchemy import TextClause, text
from sqlalchemy.exc import SQLAlchemyError

from src.repositories.repository import Repository
from src.result import Result

PAYMENT_COLUMNS = (
    "id, booking_id, amount_cents, currency, status, reason, "
    "card_last4, idempotency_key, created_at"
)

TRUNCATE_PAYMENTS: TextClause = text(
    "TRUNCATE payments RESTART IDENTITY CASCADE"
)


@dataclass(slots=True, frozen=True)
class PaymentsRepository(Repository):

    def truncate(self) -> Result[None]:
        try:
            self._session.execute(TRUNCATE_PAYMENTS)
            return Result.success(None)

        except SQLAlchemyError as err:
            return Result.failure(f"{str(err)}")

    def get_payment(self, payment_id):
        return self._session.execute(
            text(f"SELECT {PAYMENT_COLUMNS} FROM payments WHERE id = :payment_id"),
            {"payment_id": payment_id},
        ).mappings().first()

    def get_refund_for_payment(self, payment_id):
        return self._session.execute(
            text(f"SELECT {PAYMENT_COLUMNS} FROM payments WHERE idempotency_key = :key"),
            {"key": f"refund:{payment_id}"},
        ).mappings().first()

    def insert_refund(self, payment, reason):
        """Return (refund, created); the unique key arbitrates concurrent retries."""
        row = self._session.execute(
            text(
                "INSERT INTO payments (booking_id, amount_cents, currency, status, "
                "reason, card_last4, idempotency_key) "
                "VALUES (:booking_id, :amount_cents, :currency, 'refunded', "
                ":reason, :card_last4, :key) "
                "ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL "
                f"DO NOTHING RETURNING {PAYMENT_COLUMNS}"
            ),
            {"booking_id": payment["booking_id"], "amount_cents": payment["amount_cents"],
             "currency": payment["currency"], "reason": reason,
             "card_last4": payment["card_last4"], "key": f"refund:{payment['id']}"},
        ).mappings().first()
        if row is not None:
            return row, True
        return self.get_refund_for_payment(payment["id"]), False
