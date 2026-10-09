"""HTTP for payments; refund rules live in services.py."""

from flask import Blueprint, current_app, jsonify, request

from src.payments import services

bp = Blueprint("payments", __name__)


@bp.post("/payments/<int:payment_id>/refund")
def refund_payment(payment_id):
    body = request.get_json(silent=True) if request.data else {}
    if not isinstance(body, dict):
        return jsonify(error="body must be a JSON object"), 400
    payload, status = services.refund_payment(
        current_app.db, payment_id, body.get("reason", "cancellation")
    )
    return jsonify(payload), status
