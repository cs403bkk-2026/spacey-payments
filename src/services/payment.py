"""Payment business rules: recording payment attempts, idempotent retries and
refunds. No Flask here; SQL lives in the repository. Every outcome is logged as
`<event> booking_id=<id> outcome=<outcome>` - never card data or database text."""

import enum
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.domain.card import Card
from src.logger import logger
from src.models.payment import Payment, PaymentStatus
from src.repositories.payments import PaymentsRepository
from src.result import Result

# Largest value the INTEGER id columns hold.
MAX_ID: int = 2_147_483_647
MAX_IDEMPOTENCY_KEY_LENGTH: int = 255
REFUND_KEY_PREFIX: str = "refund:"
DEFAULT_REFUND_REASON: str = "cancellation"

PAYMENT_FAILED: str = "payment failed"
UNAVAILABLE: str = "payment unavailable"


class Reply(enum.Enum):
    """What happened to a request, for the route to turn into HTTP."""
    INVALID = "invalid"                    # error: the request is rejected
    DECLINED = "declined"                  # stateless attempt forced to fail
    AUTHORIZED = "authorized"              # stateless attempt accepted (card)
    RECORDED = "recorded"                  # payment: a new row
    REPLAYED = "replayed"                  # payment: the row for this key
    KEY_REUSED = "key_reused"              # error
    ALREADY_PAID = "already_paid"          # payment: the booking's success
    NOT_FOUND = "not_found"                # error
    NOT_REFUNDABLE = "not_refundable"      # error
    ALREADY_REFUNDED = "already_refunded"  # payment: the existing refund


@dataclass(slots=True, frozen=True)
class PaymentReply:
    kind: Reply
    payment: Optional[Payment] = None
    error: Optional[str] = None
    card: Optional[Card] = None


def is_id(value: Any) -> bool:
    """A positive integer that fits an id column (booleans are not integers here)."""
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= MAX_ID


def log_label(value: Any) -> Any:
    """Only well-formed ids reach the log, so a request cannot inject text."""
    return value if is_id(value) else "invalid"


def create_request_error(body: dict[str, Any]) -> Optional[str]:
    """The first problem with a POST /payments body, card fields aside."""
    if not is_id(body.get("booking_id")):
        return "booking_id must be a positive integer"

    if not is_id(body.get("amount_cents")):
        return "amount_cents must be a positive integer"

    if body.get("currency", "USD") != "USD":
        return "currency must be USD"

    key = body.get("idempotency_key")
    if not isinstance(key, str) or not key.strip():
        return "idempotency_key is required"

    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        return f"idempotency_key must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters"

    if key.startswith(REFUND_KEY_PREFIX):
        return f"idempotency_key must not start with {REFUND_KEY_PREFIX}"

    return None


def authorize_booking_payment(booking_id: int, body: dict[str, Any]) -> PaymentReply:
    """The temporary, stateless mock outcome (PT-022). Reads and writes nothing
       and does not check that the booking exists."""
    logger.debug("payment booking_id=%s outcome=started", booking_id)

    if (card := Card.from_body(body)).failed:
        logger.warning("payment booking_id=%s outcome=invalid_card", booking_id)
        return PaymentReply(Reply.INVALID, error=card.reason)

    if body.get("force_failure") is True:
        logger.warning("payment booking_id=%s outcome=failed", booking_id)
        return PaymentReply(Reply.DECLINED, error=PAYMENT_FAILED)

    logger.info("payment booking_id=%s outcome=succeeded", booking_id)
    return PaymentReply(Reply.AUTHORIZED, card=card.value)


@dataclass(slots=True)
class PaymentService:
    _session: Session
    _repository: Optional[PaymentsRepository] = field(init=False, default=None)

    @property
    def repository(self) -> PaymentsRepository:
        if self._repository is None:
            self._repository = PaymentsRepository(self._session)

        return self._repository

    @staticmethod
    def _unavailable(event: str, label: str) -> Result[Any]:
        logger.error("%s outcome=database_error", f"{event} {label}")
        return Result.failure(UNAVAILABLE)

    def create(self, body: dict[str, Any]) -> Result[PaymentReply]:
        """POST /payments: validate, honour the idempotency key, then record a
           success or (force_failure) a failed payment."""
        label = f"booking_id={log_label(body.get('booking_id'))}"
        logger.debug("payment %s outcome=started", label)

        if (error := create_request_error(body)) is not None:
            logger.warning("payment %s outcome=invalid_request", label)
            return Result.success(PaymentReply(Reply.INVALID, error=error))

        booking_id, amount_cents = body["booking_id"], body["amount_cents"]
        key: str = body["idempotency_key"]

        # A retry is answered from the ledger before anything else, so it never
        # collects twice even if the card has expired since the first attempt.
        if (existing := self.repository.get_by_idempotency_key(key)).failed:
            return self._unavailable("payment", label)
        if existing.value is not None:
            return Result.success(self._replay(existing.value, booking_id, amount_cents, label))

        if (card := Card.from_body(body)).failed:
            logger.warning("payment %s outcome=invalid_card", label)
            return Result.success(PaymentReply(Reply.INVALID, error=card.reason))

        if (paid := self.repository.get_success_for_booking(booking_id)).failed:
            return self._unavailable("payment", label)
        if paid.value is not None:
            logger.warning("payment %s outcome=already_paid", label)
            return Result.success(PaymentReply(Reply.ALREADY_PAID, payment=paid.value))

        declined = body.get("force_failure") is True
        inserted = self.repository.insert(
            booking_id=booking_id,
            amount_cents=amount_cents,
            status=PaymentStatus.FAILED if declined else PaymentStatus.SUCCESS,
            reason=PAYMENT_FAILED if declined else None,
            card_last4=card.value.last4,
            idempotency_key=key,
        )
        if inserted.failed:
            return self._unavailable("payment", label)
        if inserted.value is None:
            return self._after_conflict(key, booking_id, amount_cents, label)

        if declined:
            logger.warning("payment %s outcome=failed", label)
        else:
            logger.info("payment %s outcome=succeeded", label)
        return Result.success(PaymentReply(Reply.RECORDED, payment=inserted.value))

    def _replay(self, existing: Payment, booking_id: int, amount_cents: int,
                label: str) -> PaymentReply:
        if (existing.booking_id, existing.amount_cents) != (booking_id, amount_cents):
            logger.warning("payment %s outcome=key_reused", label)
            return PaymentReply(Reply.KEY_REUSED, error="idempotency_key reused")

        logger.info("payment %s outcome=replayed", label)
        return PaymentReply(Reply.REPLAYED, payment=existing)

    def _after_conflict(self, key: str, booking_id: int, amount_cents: int,
                        label: str) -> Result[PaymentReply]:
        """A concurrent request inserted first: answer as if it had come first."""
        if (existing := self.repository.get_by_idempotency_key(key)).failed:
            return self._unavailable("payment", label)
        if existing.value is not None:
            return Result.success(self._replay(existing.value, booking_id, amount_cents, label))

        if (paid := self.repository.get_success_for_booking(booking_id)).failed:
            return self._unavailable("payment", label)
        if paid.value is not None:
            logger.warning("payment %s outcome=already_paid", label)
            return Result.success(PaymentReply(Reply.ALREADY_PAID, payment=paid.value))

        return self._unavailable("payment", label)

    def get(self, payment_id: int) -> Result[Optional[Payment]]:
        if (found := self.repository.get(payment_id)).failed:
            return self._unavailable("payment_lookup", f"payment_id={payment_id}")

        return found

    def list_for_booking(self, booking_id: int) -> Result[list[Payment]]:
        if (found := self.repository.list_for_booking(booking_id)).failed:
            return self._unavailable("payment_list", f"booking_id={booking_id}")

        return found

    def refund(self, payment_id: int, body: dict[str, Any]) -> Result[PaymentReply]:
        """POST /payments/<id>/refund: a full refund recorded as a new
           'refunded' row keyed 'refund:<payment_id>'. The original row is
           never changed, and a second refund returns the first."""
        logger.debug("refund payment_id=%s outcome=started", payment_id)

        reason = body.get("reason", DEFAULT_REFUND_REASON)
        if not isinstance(reason, str) or not reason.strip():
            logger.warning("refund payment_id=%s outcome=invalid_request", payment_id)
            return Result.success(
                PaymentReply(Reply.INVALID, error="reason must be a non-empty string"))

        if (found := self.repository.get(payment_id)).failed:
            return self._unavailable("refund", f"payment_id={payment_id}")
        if (payment := found.value) is None:
            logger.warning("refund payment_id=%s outcome=not_found", payment_id)
            return Result.success(PaymentReply(Reply.NOT_FOUND, error="payment not found"))

        label = f"booking_id={payment.booking_id}"
        if payment.status != PaymentStatus.SUCCESS:
            logger.warning("refund %s outcome=not_refundable", label)
            return Result.success(
                PaymentReply(Reply.NOT_REFUNDABLE, error="payment is not refundable"))

        key = f"{REFUND_KEY_PREFIX}{payment_id}"
        if (existing := self.repository.get_by_idempotency_key(key)).failed:
            return self._unavailable("refund", label)
        if existing.value is not None:
            logger.info("refund %s outcome=already_refunded", label)
            return Result.success(PaymentReply(Reply.ALREADY_REFUNDED, payment=existing.value))

        inserted = self.repository.insert(
            booking_id=payment.booking_id,
            amount_cents=payment.amount_cents,
            currency=payment.currency,
            status=PaymentStatus.REFUNDED,
            reason=reason.strip(),
            card_last4=payment.card_last4,
            idempotency_key=key,
        )
        if inserted.failed:
            return self._unavailable("refund", label)
        if inserted.value is None:
            # A concurrent refund of the same payment won the unique index.
            if (existing := self.repository.get_by_idempotency_key(key)).failed \
                    or existing.value is None:
                return self._unavailable("refund", label)
            logger.info("refund %s outcome=already_refunded", label)
            return Result.success(PaymentReply(Reply.ALREADY_REFUNDED, payment=existing.value))

        logger.info("refund %s outcome=refunded", label)
        return Result.success(PaymentReply(Reply.RECORDED, payment=inserted.value))
