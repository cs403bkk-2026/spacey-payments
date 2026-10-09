"""Payment business rules: the (mocked) payment decision.
No Flask and no SQL - HTTP lives in api.py, the database in repository.py."""

import psycopg

from src.logger import logger
from src.payments import repository
from src.payments.models import cards


def pay_booking(db, booking_id, card_number, expiry, cvc, force_failure=False):
    """Mocked payment: no provider, so it succeeds unless force_failure is set
    or the card doesn't look valid (see cards.validate_card). Paying an already-paid
    booking is a no-op rather than an error, so a retried request can't break
    the flow or charge twice - and doesn't need a card either. Only the card's
    last 4 digits are ever stored.
    Returns (payload, status) - the booking, or an {"error": ...}.
    Every outcome is logged: DEBUG start, INFO success/already paid, WARNING
    rejections, ERROR database failures."""
    logger.debug("payment booking_id=%s outcome=started", booking_id)
    try:
        booking = repository.get_booking(db, booking_id)
        if booking is None:
            logger.warning("payment booking_id=%s outcome=not_found", booking_id)
            return {"error": "booking not found"}, 404

        if booking["paid"]:
            logger.info("payment booking_id=%s outcome=already_paid", booking_id)
            return booking, 200

        card_error = cards.validate_card(card_number, expiry, cvc)
        if card_error:
            logger.warning("payment booking_id=%s outcome=invalid_card", booking_id)
            return {"error": card_error}, 400

        if force_failure:
            logger.warning("payment booking_id=%s outcome=failed", booking_id)
            return {"error": "payment failed"}, 402

        booking = repository.mark_paid(db, booking_id, card_number[-4:])
        logger.info("payment booking_id=%s outcome=succeeded", booking_id)
        return booking, 200
    except psycopg.Error:
        # Database diagnostics may include SQL parameters; never log the exception.
        logger.error("payment booking_id=%s outcome=database_error", booking_id)
        return {"error": "payment unavailable"}, 500
