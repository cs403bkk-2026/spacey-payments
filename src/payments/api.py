"""HTTP for payments. Parses requests and shapes responses; the rules live in
services.py."""

from flask import Blueprint, current_app, jsonify, request

from src.payments import services

bp = Blueprint("payments", __name__)


@bp.post("/bookings/<int:booking_id>/pay")
def pay_booking(booking_id):
    body = request.get_json(silent=True) or {}
    payload, status = services.pay_booking(
        current_app.db,
        booking_id,
        body.get("card_number"),
        body.get("expiry"),
        body.get("cvc"),
        force_failure=body.get("force_failure") is True,
    )
    return jsonify(payload), status
