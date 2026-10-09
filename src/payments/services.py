"""Payment business rules. No Flask and no SQL - HTTP lives in api.py, the
database in repository.py. Card validation lives in models/cards.py."""

from psycopg import Error as DatabaseError

from src.logger import logger
from src.payments import repository


def refund_payment(db, payment_id, reason="cancellation"):
    """Record a full mock refund, leaving the original payment untouched."""
    booking_id = None
    try:
        payment = repository.get_payment(db, payment_id)
        if payment is None:
            logger.warning("payment booking_id=%s outcome=not_found", booking_id)
            return {"error": "payment not found"}, 404
        booking_id = payment["booking_id"]
        logger.debug("payment booking_id=%s outcome=refund_started", booking_id)
        if not isinstance(reason, str) or not reason.strip():
            logger.warning("payment booking_id=%s outcome=invalid_reason", booking_id)
            return {"error": "reason must be a non-empty string"}, 400
        if payment["status"] != "success":
            logger.warning("payment booking_id=%s outcome=not_refundable", booking_id)
            return {"error": "payment is not refundable"}, 409
        refund, created = repository.insert_refund(db, payment, reason)
        logger.info(
            "payment booking_id=%s outcome=%s", booking_id,
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
    except DatabaseError:
        logger.error("payment booking_id=%s outcome=database_error", booking_id)
        return {"error": "payment unavailable"}, 500
