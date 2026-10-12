from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from src.logger import logger
from src.repositories.payments import PaymentsRepository


@dataclass(slots=True)
class PaymentService:
    _session: Session
    booking_id: Optional[int] = field(init=False, default=None)
    _repository: Optional[PaymentsRepository] = field(init=False, default=None)

    @property
    def repository(self) -> PaymentsRepository:
        if self._repository is None:
            self._repository = PaymentsRepository(self._session)

        return self._repository

    def refund_payment(self, payment_id, reason="cancellation"):
        """Record a full mock refund, leaving the original payment untouched."""
        self.booking_id = None
        payment = self.repository.get_payment(payment_id)
        if payment is None:
            logger.warning("payment booking_id=%s outcome=not_found", self.booking_id)
            return {"error": "payment not found"}, 404
        self.booking_id = payment["booking_id"]
        logger.debug("payment booking_id=%s outcome=refund_started", self.booking_id)
        if not isinstance(reason, str) or not reason.strip():
            logger.warning("payment booking_id=%s outcome=invalid_reason", self.booking_id)
            return {"error": "reason must be a non-empty string"}, 400
        if payment["status"] != "success":
            logger.warning("payment booking_id=%s outcome=not_refundable", self.booking_id)
            return {"error": "payment is not refundable"}, 409
        refund, created = self.repository.insert_refund(payment, reason)
        logger.info(
            "payment booking_id=%s outcome=%s", self.booking_id,
            "refunded" if created else "already_refunded",
        )
        return {
            "payment_id": refund["id"],
            "booking_id": refund["booking_id"],
            "amount_cents": refund["amount_cents"],
            "currency": refund["currency"],
            "status": refund["status"],
            "card_last4": refund["card_last4"],
            "reason": refund["reason"],
            "created_at": refund["created_at"].isoformat(),
        }, 201 if created else 200
