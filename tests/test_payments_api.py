"""The ledger endpoints in openapi.yaml: POST /payments, GET /payments,
GET /payments/<id> and POST /payments/<id>/refund, plus service-token auth."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from unittest import mock

from src.models.payment import PaymentStatus
from src.repositories.payments import PaymentsRepository
from src.result import Result
from tests.support import AUTH, SERVICE_TOKEN, VALID_CARD, DatabaseTestCase, unreachable_database

PAYMENT_FIELDS = {"payment_id", "booking_id", "amount_cents", "currency", "status",
                  "reason", "card_last4", "created_at"}


def payment_request(**overrides):
    return {"booking_id": 42, "amount_cents": 1500, "currency": "USD",
            **VALID_CARD, "idempotency_key": "booking-42-attempt-1", **overrides}


class PaymentsApiTestCase(DatabaseTestCase):
    def post_payment(self, **overrides):
        return self.client.post("/payments", json=payment_request(**overrides), headers=AUTH)

    def refund(self, payment_id, **kwargs):
        return self.client.post(f"/payments/{payment_id}/refund", headers=AUTH, **kwargs)

    def assert_payment_body(self, body, **expected):
        self.assertEqual(set(body), PAYMENT_FIELDS)
        datetime.fromisoformat(body["created_at"])
        self.assertTrue(body["created_at"].endswith("+00:00"))
        for key, value in expected.items():
            self.assertEqual(body[key], value, key)

    def assert_no_card_data(self, text):
        for value in (VALID_CARD["card_number"], VALID_CARD["cvc"], VALID_CARD["expiry"]):
            self.assertNotIn(value, text)


class AuthTests(PaymentsApiTestCase):
    ENDPOINTS = [
        ("post", "/payments"),
        ("get", "/payments?booking_id=42"),
        ("get", "/payments/1"),
        ("post", "/payments/1/refund"),
        ("post", "/payment/bookings/7/pay"),
    ]

    def test_missing_or_wrong_token_is_401_and_logged(self):
        for headers in ({}, {"X-Service-Token": "wrong"}, {"X-Service-Token": ""}):
            for method, path in self.ENDPOINTS:
                with self.subTest(headers=headers, path=path):
                    with self.assertLogs("spacey_payments", level="WARNING") as logs:
                        resp = getattr(self.client, method)(path, json={}, headers=headers)
                    self.assertEqual(resp.status_code, 401)
                    self.assertEqual(resp.get_json(), {"error": "unauthorized"})
                    self.assertEqual([r.getMessage() for r in logs.records],
                                     ["auth outcome=unauthorized"])
        self.assertEqual(self.count_payments(), 0)

    def test_unset_service_token_rejects_even_an_empty_header(self):
        with mock.patch("src.config.SERVICE_TOKEN", ""):
            with self.assertLogs("spacey_payments", level="WARNING"):
                resp = self.client.get("/payments/1", headers={"X-Service-Token": ""})
        self.assertEqual(resp.status_code, 401)

    def test_health_needs_no_token(self):
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_token_is_not_logged(self):
        with self.assertLogs("spacey_payments", level="DEBUG") as logs:
            self.post_payment()
            self.client.get("/payments/1", headers={"X-Service-Token": "wrong-secret"})
        self.assertNotIn(SERVICE_TOKEN, "\n".join(logs.output))
        self.assertNotIn("wrong-secret", "\n".join(logs.output))


class CreatePaymentTests(PaymentsApiTestCase):
    def test_success_is_201_and_records_only_last4(self):
        resp = self.post_payment()

        self.assertEqual(resp.status_code, 201)
        self.assert_payment_body(resp.get_json(), payment_id=1, booking_id=42,
                                 amount_cents=1500, currency="USD", status="success",
                                 reason=None, card_last4="4242")
        self.assert_no_card_data(resp.get_data(as_text=True))
        [row] = self.all_payments()
        self.assertEqual((row.status, row.card_last4, row.idempotency_key),
                         (PaymentStatus.SUCCESS, "4242", "booking-42-attempt-1"))

    def test_currency_defaults_to_usd(self):
        body = payment_request()
        del body["currency"]
        resp = self.client.post("/payments", json=body, headers=AUTH)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["currency"], "USD")

    def test_force_failure_is_402_with_the_recorded_failed_payment(self):
        resp = self.post_payment(force_failure=True)

        self.assertEqual(resp.status_code, 402)
        self.assert_payment_body(resp.get_json(), status="failed",
                                 reason="payment failed", card_last4="4242")
        self.assertEqual(self.all_payments()[0].status, PaymentStatus.FAILED)

    def test_only_a_literal_true_forces_failure(self):
        for index, value in enumerate(("true", 1, None, False)):
            with self.subTest(force_failure=value):
                resp = self.post_payment(booking_id=100 + index, force_failure=value,
                                         idempotency_key=f"key-{index}")
                self.assertEqual(resp.status_code, 201)

    def test_retry_with_the_same_key_replays_without_collecting_again(self):
        first = self.post_payment()
        second = self.post_payment()

        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json(), first.get_json())
        self.assertEqual(self.count_payments(), 1)

    def test_retry_of_a_failed_payment_replays_the_402(self):
        first = self.post_payment(force_failure=True)
        second = self.post_payment(force_failure=False)

        self.assertEqual(second.status_code, 402)
        self.assertEqual(second.get_json(), first.get_json())
        self.assertEqual(self.count_payments(), 1)

    def test_retry_is_answered_even_if_the_card_is_now_invalid(self):
        first = self.post_payment()
        second = self.post_payment(expiry="01/20")
        self.assertEqual((second.status_code, second.get_json()), (201, first.get_json()))

    def test_key_reused_for_another_booking_or_amount_is_409(self):
        self.post_payment()
        for overrides in ({"booking_id": 43}, {"amount_cents": 1600}):
            with self.subTest(**overrides):
                resp = self.post_payment(**overrides)
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(resp.get_json(), {"error": "idempotency_key reused"})
        self.assertEqual(self.count_payments(), 1)

    def test_new_key_after_a_failure_creates_a_new_payment(self):
        failed = self.post_payment(force_failure=True).get_json()
        retry = self.post_payment(idempotency_key="booking-42-attempt-2")

        self.assertEqual(retry.status_code, 201)
        self.assertNotEqual(retry.get_json()["payment_id"], failed["payment_id"])
        self.assertEqual([p.status for p in self.all_payments()],
                         [PaymentStatus.FAILED, PaymentStatus.SUCCESS])

    def test_paid_booking_with_another_key_is_409_with_the_existing_payment(self):
        paid = self.post_payment().get_json()
        for overrides in ({}, {"force_failure": True}):
            with self.subTest(**overrides):
                resp = self.post_payment(idempotency_key="booking-42-attempt-2", **overrides)
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(resp.get_json(), paid)
        self.assertEqual(self.count_payments(), 1)

    def test_invalid_body_is_400_and_records_nothing(self):
        cases = [
            ({"booking_id": None}, "booking_id must be a positive integer"),
            ({"booking_id": "42"}, "booking_id must be a positive integer"),
            ({"booking_id": 0}, "booking_id must be a positive integer"),
            ({"booking_id": True}, "booking_id must be a positive integer"),
            ({"booking_id": 2**31}, "booking_id must be a positive integer"),
            ({"amount_cents": 0}, "amount_cents must be a positive integer"),
            ({"amount_cents": -100}, "amount_cents must be a positive integer"),
            ({"amount_cents": 15.5}, "amount_cents must be a positive integer"),
            ({"amount_cents": 2**31}, "amount_cents must be a positive integer"),
            ({"currency": "EUR"}, "currency must be USD"),
            ({"idempotency_key": None}, "idempotency_key is required"),
            ({"idempotency_key": "  "}, "idempotency_key is required"),
            ({"idempotency_key": 7}, "idempotency_key is required"),
            ({"idempotency_key": "k" * 256}, "idempotency_key must be at most 255 characters"),
            ({"idempotency_key": "refund:1"}, "idempotency_key must not start with refund:"),
            ({"card_number": "4242"}, "card_number must be 13-19 digits"),
            ({"card_number": None}, "card_number must be 13-19 digits"),
            ({"card_number": "4242424242424241"}, "card_number is not a valid card number"),
            ({"cvc": "1"}, "cvc must be 3 or 4 digits"),
            ({"expiry": "13/30"}, "expiry must be in MM/YY format"),
            ({"expiry": "01/20"}, "card has expired"),
        ]
        for overrides, message in cases:
            with self.subTest(**{k: str(v)[:20] for k, v in overrides.items()}):
                resp = self.post_payment(**overrides)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json(), {"error": message})
        self.assertEqual(self.count_payments(), 0)

    def test_body_that_is_not_a_json_object_is_400(self):
        for data in ("not json", "[]", "null", "42", ""):
            with self.subTest(data=data):
                resp = self.client.post("/payments", data=data, headers=AUTH,
                                        content_type="application/json")
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json(), {"error": "body must be a JSON object"})

    def test_concurrent_requests_with_the_same_key_record_one_payment(self):
        responses = self.run_concurrently(lambda client: client.post(
            "/payments", json=payment_request(), headers=AUTH))

        self.assertEqual([r.status_code for r in responses], [201, 201])
        self.assertEqual(responses[0].get_json(), responses[1].get_json())
        self.assertEqual(self.count_payments(), 1)

    def test_concurrent_requests_with_different_keys_collect_once(self):
        keys = iter(("key-a", "key-b"))
        responses = self.run_concurrently(lambda client: client.post(
            "/payments", json=payment_request(idempotency_key=next(keys)), headers=AUTH))

        self.assertEqual(sorted(r.status_code for r in responses), [201, 409])
        self.assertEqual(responses[0].get_json()["payment_id"],
                         responses[1].get_json()["payment_id"])
        self.assertEqual(self.count_payments(), 1)

    def run_concurrently(self, request):
        """Both requests pass their lookups before either inserts, so the
        unique indexes, not the lookups, have to settle the race."""
        both_looked = Barrier(2, timeout=5)
        waited = threading.local()
        original = PaymentsRepository.get_success_for_booking

        def get_success_then_wait(repository, booking_id):
            result = original(repository, booking_id)
            if not getattr(waited, "done", False):  # only the first lookup per request
                waited.done = True
                both_looked.wait()
            return result

        with mock.patch.object(PaymentsRepository, "get_success_for_booking",
                               get_success_then_wait):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(request, self.app.test_client()) for _ in range(2)]
                return [future.result(timeout=10) for future in futures]

    def test_logs_outcomes_at_the_right_level_without_card_data(self):
        cases = [
            ({}, 201, logging.INFO, "succeeded"),
            ({}, 201, logging.INFO, "replayed"),
            ({"idempotency_key": "other"}, 409, logging.WARNING, "already_paid"),
            ({"amount_cents": 1}, 409, logging.WARNING, "key_reused"),
            ({"booking_id": 7, "idempotency_key": "k7", "force_failure": True},
             402, logging.WARNING, "failed"),
            ({"booking_id": 8, "idempotency_key": "k8", "cvc": "1"},
             400, logging.WARNING, "invalid_card"),
            ({"booking_id": "4242424242424242"}, 400, logging.WARNING, "invalid_request"),
        ]
        for overrides, status, level, outcome in cases:
            with self.subTest(outcome=outcome):
                with self.assertLogs("spacey_payments", level="DEBUG") as logs:
                    resp = self.post_payment(**overrides)
                self.assertEqual(resp.status_code, status)
                booking = overrides.get("booking_id", 42)
                booking = booking if isinstance(booking, int) else "invalid"
                self.assertEqual(
                    [(r.levelno, r.getMessage()) for r in logs.records],
                    [(logging.DEBUG, f"payment booking_id={booking} outcome=started"),
                     (level, f"payment booking_id={booking} outcome={outcome}")])
                self.assert_no_card_data("\n".join(logs.output))

    def test_database_failure_is_500_and_logged_without_details(self):
        with unreachable_database():
            with self.assertLogs("spacey_payments", level="DEBUG") as logs:
                resp = self.post_payment()

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json(), {"error": "payment unavailable"})
        last = logs.records[-1]
        self.assertEqual((last.levelno, last.getMessage()),
                         (logging.ERROR, "payment booking_id=42 outcome=database_error"))
        self.assertIsNone(last.exc_info)
        self.assertNotIn("private-password", "\n".join(logs.output))
        self.assertNotIn("127.0.0.1", resp.get_data(as_text=True))

    def test_failed_insert_is_500_and_records_nothing(self):
        with mock.patch.object(PaymentsRepository, "insert",
                               return_value=Result.failure("INSERT ... 4242")):
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                resp = self.post_payment()
        self.assertEqual((resp.status_code, resp.get_json()),
                         (500, {"error": "payment unavailable"}))
        self.assertNotIn("INSERT", "\n".join(logs.output))
        self.assertEqual(self.count_payments(), 0)


class GetPaymentTests(PaymentsApiTestCase):
    def test_returns_the_payment(self):
        created = self.post_payment().get_json()
        resp = self.client.get(f"/payments/{created['payment_id']}", headers=AUTH)
        self.assertEqual((resp.status_code, resp.get_json()), (200, created))

    def test_unknown_payment_is_404(self):
        for payment_id in ("999", "2147483648"):
            with self.subTest(payment_id=payment_id):
                resp = self.client.get(f"/payments/{payment_id}", headers=AUTH)
                self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.client.get("/payments/999", headers=AUTH).get_json(),
                         {"error": "payment not found"})

    def test_non_numeric_or_zero_id_is_404(self):
        for payment_id in ("abc", "0", "-1"):
            with self.subTest(payment_id=payment_id):
                self.assertEqual(
                    self.client.get(f"/payments/{payment_id}", headers=AUTH).status_code, 404)

    def test_idempotency_key_is_not_returned(self):
        self.insert_payment(idempotency_key="secret-key")
        body = self.client.get("/payments/1", headers=AUTH).get_data(as_text=True)
        self.assertNotIn("secret-key", body)
        self.assertNotIn("idempotency_key", body)

    def test_database_failure_is_500(self):
        with unreachable_database():
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                resp = self.client.get("/payments/1", headers=AUTH)
        self.assertEqual((resp.status_code, resp.get_json()),
                         (500, {"error": "payment unavailable"}))
        self.assertEqual([r.getMessage() for r in logs.records],
                         ["payment_lookup payment_id=1 outcome=database_error"])


class ListPaymentsTests(PaymentsApiTestCase):
    def test_lists_a_bookings_payments_oldest_first(self):
        self.post_payment(force_failure=True)
        self.post_payment(booking_id=99, idempotency_key="other-booking")
        success = self.post_payment(idempotency_key="attempt-2").get_json()
        self.refund(success["payment_id"])

        resp = self.client.get("/payments?booking_id=42", headers=AUTH)

        self.assertEqual(resp.status_code, 200)
        payments = resp.get_json()["payments"]
        self.assertEqual([p["status"] for p in payments], ["failed", "success", "refunded"])
        self.assertEqual({p["booking_id"] for p in payments}, {42})
        ids = [p["payment_id"] for p in payments]
        self.assertEqual(ids, sorted(ids))

    def test_booking_without_payments_is_an_empty_list(self):
        resp = self.client.get("/payments?booking_id=42", headers=AUTH)
        self.assertEqual((resp.status_code, resp.get_json()), (200, {"payments": []}))

    def test_missing_or_bad_booking_id_is_400(self):
        for query in ("", "?booking_id=", "?booking_id=abc", "?booking_id=-1",
                      "?booking_id=0", "?booking_id=1.5", "?booking_id=2147483648",
                      "?booking_id=%C2%B2"):
            with self.subTest(query=query):
                resp = self.client.get(f"/payments{query}", headers=AUTH)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json(),
                                 {"error": "booking_id must be a positive integer"})

    def test_database_failure_is_500(self):
        with unreachable_database():
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                resp = self.client.get("/payments?booking_id=42", headers=AUTH)
        self.assertEqual(resp.status_code, 500)
        self.assertEqual([r.getMessage() for r in logs.records],
                         ["payment_list booking_id=42 outcome=database_error"])


class RefundTests(PaymentsApiTestCase):
    def setUp(self):
        super().setUp()
        self.paid = self.post_payment().get_json()
        self.payment_id = self.paid["payment_id"]

    def test_refund_is_201_with_a_new_refunded_row(self):
        resp = self.refund(self.payment_id)

        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assert_payment_body(body, booking_id=42, amount_cents=1500, currency="USD",
                                 status="refunded", reason="cancellation",
                                 card_last4="4242")
        self.assertNotEqual(body["payment_id"], self.payment_id)
        original, refund = self.all_payments()
        self.assertEqual(refund.idempotency_key, f"refund:{self.payment_id}")
        self.assertEqual(original.status, PaymentStatus.SUCCESS)
        self.assertEqual(self.client.get(f"/payments/{self.payment_id}", headers=AUTH)
                         .get_json(), self.paid)

    def test_reason_is_stored(self):
        resp = self.refund(self.payment_id, json={"reason": "hold_expired"})
        self.assertEqual(resp.get_json()["reason"], "hold_expired")

    def test_second_refund_returns_the_first_with_200(self):
        first = self.refund(self.payment_id).get_json()
        second = self.refund(self.payment_id, json={"reason": "hold_expired"})

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json(), first)
        self.assertEqual(self.count_payments(), 2)

    def test_concurrent_refunds_record_one_refund(self):
        both_looked = Barrier(2, timeout=5)
        waited = threading.local()
        original = PaymentsRepository.get_by_idempotency_key

        def lookup_then_wait(repository, key):
            result = original(repository, key)
            if not getattr(waited, "done", False):  # only the first lookup per request
                waited.done = True
                both_looked.wait()
            return result

        with mock.patch.object(PaymentsRepository, "get_by_idempotency_key",
                               lookup_then_wait):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.app.test_client().post,
                                       f"/payments/{self.payment_id}/refund", headers=AUTH)
                           for _ in range(2)]
                responses = [future.result(timeout=10) for future in futures]

        self.assertEqual(sorted(r.status_code for r in responses), [200, 201])
        self.assertEqual(responses[0].get_json(), responses[1].get_json())
        self.assertEqual(self.count_payments(), 2)

    def test_unknown_payment_is_404(self):
        resp = self.refund(999)
        self.assertEqual((resp.status_code, resp.get_json()),
                         (404, {"error": "payment not found"}))

    def test_payment_that_is_not_success_is_409(self):
        refund_id = self.refund(self.payment_id).get_json()["payment_id"]
        failed = self.insert_payment(booking_id=7, status=PaymentStatus.FAILED).id
        unknown = self.insert_payment(booking_id=8, status=PaymentStatus.UNKNOWN).id

        for payment_id in (failed, unknown, refund_id):
            with self.subTest(payment_id=payment_id):
                resp = self.refund(payment_id)
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(resp.get_json(), {"error": "payment is not refundable"})
        self.assertEqual(self.count_payments(), 4)

    def test_bad_body_or_reason_is_400_and_records_nothing(self):
        cases = [
            (dict(data="not json", content_type="application/json"),
             "body must be a JSON object"),
            (dict(json=[]), "body must be a JSON object"),
            (dict(json="cancellation"), "body must be a JSON object"),
            (dict(json={"reason": ""}), "reason must be a non-empty string"),
            (dict(json={"reason": "   "}), "reason must be a non-empty string"),
            (dict(json={"reason": None}), "reason must be a non-empty string"),
            (dict(json={"reason": 5}), "reason must be a non-empty string"),
        ]
        for kwargs, message in cases:
            with self.subTest(kwargs=kwargs):
                resp = self.refund(self.payment_id, **kwargs)
                self.assertEqual((resp.status_code, resp.get_json()), (400, {"error": message}))
        self.assertEqual(self.count_payments(), 1)

    def test_empty_body_or_object_defaults_to_cancellation(self):
        resp = self.refund(self.payment_id, json={})
        self.assertEqual((resp.status_code, resp.get_json()["reason"]), (201, "cancellation"))

    def test_logs_each_outcome(self):
        failed = self.insert_payment(booking_id=7, status=PaymentStatus.FAILED).id
        cases = [
            (self.payment_id, logging.INFO, "refund booking_id=42 outcome=refunded"),
            (self.payment_id, logging.INFO, "refund booking_id=42 outcome=already_refunded"),
            (failed, logging.WARNING, "refund booking_id=7 outcome=not_refundable"),
            (999, logging.WARNING, "refund payment_id=999 outcome=not_found"),
        ]
        for payment_id, level, message in cases:
            with self.subTest(message=message):
                with self.assertLogs("spacey_payments", level="DEBUG") as logs:
                    self.refund(payment_id)
                self.assertEqual(
                    [(r.levelno, r.getMessage()) for r in logs.records],
                    [(logging.DEBUG, f"refund payment_id={payment_id} outcome=started"),
                     (level, message)])

    def test_database_failure_is_500(self):
        with mock.patch.object(PaymentsRepository, "insert",
                               return_value=Result.failure("db text")):
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                resp = self.refund(self.payment_id)
        self.assertEqual((resp.status_code, resp.get_json()),
                         (500, {"error": "payment unavailable"}))
        self.assertEqual([r.getMessage() for r in logs.records],
                         ["refund booking_id=42 outcome=database_error"])
        self.assertEqual(self.count_payments(), 1)
