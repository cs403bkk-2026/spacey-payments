"""HTTP for payments; the Unit of Work commits before returning success."""

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from src.logger import logger
from src.unit_of_work import UnitOfWork

payment_blueprint = Blueprint("payments", __name__)


@payment_blueprint.post("/payments/<int:payment_id>/refund")
def refund_payment(payment_id):
    body = request.get_json(silent=True) if request.data else {}
    if not isinstance(body, dict):
        return jsonify(error="body must be a JSON object"), 400
    service = None
    try:
        with UnitOfWork().transaction() as services:
            service = services.payments
            payload, status = service.refund_payment(payment_id, body.get("reason", "cancellation"))
        return jsonify(payload), status
    except SQLAlchemyError:
        logger.error("payment booking_id=%s outcome=database_error",
                     service.booking_id if service is not None else None)
        return jsonify(error="payment unavailable"), 500
