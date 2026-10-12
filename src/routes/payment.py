"""Payment endpoints (openapi.yaml). HTTP only: parse the request, call the
service inside a unit of work, and turn its reply into a status code and body."""

from datetime import timezone
from hmac import compare_digest
from typing import Any, Optional

from flask import Blueprint, Response, jsonify, request

from src import config
from src.logger import logger
from src.models.payment import Payment, PaymentStatus
from src.services.payment import (
    UNAVAILABLE,
    PaymentReply,
    Reply,
    authorize_booking_payment,
    is_id,
)
from src.unit_of_work import UnitOfWork

payment_blueprint: Blueprint = Blueprint("payments", __name__)

# Path ids are capped at the INTEGER column's range, so larger ones are a 404.
ID: str = "int(min=1, max=2147483647)"

# A recorded (or replayed) payment answers with the status its outcome had.
STATUS_BY_PAYMENT: dict[PaymentStatus, int] = {
    PaymentStatus.SUCCESS: 201,
    PaymentStatus.FAILED: 402,
    PaymentStatus.UNKNOWN: 202,
    PaymentStatus.REFUNDED: 201,
}
STATUS_BY_ERROR: dict[Reply, int] = {
    Reply.INVALID: 400,
    Reply.DECLINED: 402,
    Reply.NOT_FOUND: 404,
    Reply.KEY_REUSED: 409,
    Reply.NOT_REFUNDABLE: 409,
}

type JsonResponse = tuple[Response, int]


@payment_blueprint.before_request
def require_service_token() -> Optional[JsonResponse]:
    """Every payment endpoint needs X-Service-Token; an unset SERVICE_TOKEN
       rejects everything rather than leaving the endpoints open."""
    expected: str = config.SERVICE_TOKEN
    given: str = request.headers.get("X-Service-Token", "")
    if not expected or not compare_digest(given.encode(), expected.encode()):
        logger.warning("auth outcome=unauthorized")
        return error_response("unauthorized", 401)

    return None


def error_response(message: str, status: int) -> JsonResponse:
    return jsonify(error=message), status


def payment_body(payment: Payment) -> dict[str, Any]:
    """The API shape of a ledger row. The idempotency key is never returned."""
    return {
        "payment_id": payment.id,
        "booking_id": payment.booking_id,
        "amount_cents": payment.amount_cents,
        "currency": payment.currency.value,
        "status": payment.status.value,
        "reason": payment.reason,
        "card_last4": payment.card_last4,
        "created_at": payment.created_at.astimezone(timezone.utc).isoformat(),
    }


def reply_response(reply: PaymentReply) -> JsonResponse:
    if reply.kind in STATUS_BY_ERROR:
        return error_response(reply.error, STATUS_BY_ERROR[reply.kind])

    if reply.kind == Reply.ALREADY_PAID:
        return jsonify(payment_body(reply.payment)), 409

    if reply.kind == Reply.ALREADY_REFUNDED:
        return jsonify(payment_body(reply.payment)), 200

    return jsonify(payment_body(reply.payment)), STATUS_BY_PAYMENT[reply.payment.status]


def json_object_body(empty_is_object: bool = False) -> Optional[dict[str, Any]]:
    """The JSON object body, or None if it is malformed or not an object."""
    if empty_is_object and not request.get_data():
        return {}

    body = request.get_json(silent=True, force=True)
    return body if isinstance(body, dict) else None


@payment_blueprint.post(f"/payment/bookings/<{ID}:booking_id>/pay")
def pay_booking(booking_id: int) -> JsonResponse:
    """Temporary and stateless (PT-022). A missing, malformed or non-object
       body is read as {} and gets the first card error."""
    body = request.get_json(silent=True)
    reply = authorize_booking_payment(booking_id, body if isinstance(body, dict) else {})

    if reply.kind == Reply.AUTHORIZED:
        return jsonify(booking_id=booking_id, status="success",
                       card_last4=reply.card.last4), 200

    return error_response(reply.error, STATUS_BY_ERROR[reply.kind])


@payment_blueprint.post("/payments")
def create_payment() -> JsonResponse:
    if (body := json_object_body()) is None:
        return error_response("body must be a JSON object", 400)

    with UnitOfWork().transaction() as services:
        result = services.payments.create(body)

    if result.failed:
        return error_response(UNAVAILABLE, 500)

    return reply_response(result.value)


@payment_blueprint.get("/payments")
def list_payments() -> JsonResponse:
    raw: str = request.args.get("booking_id", "")
    booking_id: Optional[int] = int(raw) if raw.isascii() and raw.isdigit() else None
    if not is_id(booking_id):
        return error_response("booking_id must be a positive integer", 400)

    with UnitOfWork().transaction() as services:
        result = services.payments.list_for_booking(booking_id)

    if result.failed:
        return error_response(UNAVAILABLE, 500)

    return jsonify(payments=[payment_body(payment) for payment in result.value]), 200


@payment_blueprint.get(f"/payments/<{ID}:payment_id>")
def get_payment(payment_id: int) -> JsonResponse:
    with UnitOfWork().transaction() as services:
        result = services.payments.get(payment_id)

    if result.failed:
        return error_response(UNAVAILABLE, 500)

    if result.value is None:
        return error_response("payment not found", 404)

    return jsonify(payment_body(result.value)), 200


@payment_blueprint.post(f"/payments/<{ID}:payment_id>/refund")
def refund_payment(payment_id: int) -> JsonResponse:
    if (body := json_object_body(empty_is_object=True)) is None:
        return error_response("body must be a JSON object", 400)

    with UnitOfWork().transaction() as services:
        result = services.payments.refund(payment_id, body)

    if result.failed:
        return error_response(UNAVAILABLE, 500)

    return reply_response(result.value)
