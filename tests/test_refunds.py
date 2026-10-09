from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import psycopg

from src.app import create_app
from src.payments import repository
from tests.support import AppTestCase


class RefundTests(AppTestCase):
    def seed_payment(self, status="success"):
        with self.app.db.cursor() as cur:
            cur.execute(
                "INSERT INTO payments (booking_id, amount_cents, status, card_last4) "
                "VALUES (42, 1250, %s, '4242') RETURNING id",
                (status,),
            )
            return cur.fetchone()["id"]

    def refund(self, payment_id, **kwargs):
        return self.client.post(f"/payments/{payment_id}/refund", **kwargs)

    def test_full_refund_and_retry_preserve_original(self):
        payment_id = self.seed_payment()
        original = repository.get_payment(self.app.db, payment_id)
        with self.assertLogs("spacey_payments", level="DEBUG") as logs:
            first = self.refund(payment_id)
            retry = self.refund(payment_id, json={"reason": "different reason"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.get_json(), retry.get_json())
        payload = first.get_json()
        self.assertEqual(set(payload), {
            "payment_id", "booking_id", "amount_cents", "currency", "status",
            "card_last4", "reason", "created_at",
        })
        self.assertEqual(payload["booking_id"], 42)
        self.assertEqual(payload["amount_cents"], 1250)
        self.assertEqual(payload["currency"], "USD")
        self.assertEqual(payload["status"], "refunded")
        self.assertEqual(payload["card_last4"], "4242")
        self.assertEqual(payload["reason"], "cancellation")
        refund = repository.get_refund_for_payment(self.app.db, payment_id)
        self.assertEqual(refund["id"], payload["payment_id"])
        self.assertEqual(refund["idempotency_key"], f"refund:{payment_id}")
        self.assertEqual(repository.get_payment(self.app.db, payment_id), original)
        with self.app.db.cursor() as cur:
            cur.execute("SELECT count(*) AS count FROM payments")
            self.assertEqual(cur.fetchone()["count"], 2)
        self.assertEqual(
            [(r.levelname, r.getMessage()) for r in logs.records],
            [("DEBUG", "payment booking_id=42 outcome=refund_started"),
             ("INFO", "payment booking_id=42 outcome=refunded"),
             ("DEBUG", "payment booking_id=42 outcome=refund_started"),
             ("INFO", "payment booking_id=42 outcome=already_refunded")],
        )

    def test_custom_reason(self):
        response = self.refund(self.seed_payment(), json={"reason": "hold expired"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["reason"], "hold expired")

    def test_non_success_payments_are_not_refundable(self):
        for status in ("failed", "unknown", "refunded"):
            with self.subTest(status=status):
                payment_id = self.seed_payment(status)
                with self.assertLogs("spacey_payments", level="WARNING") as logs:
                    response = self.refund(payment_id)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.get_json(), {"error": "payment is not refundable"})
                self.assertIsNone(repository.get_refund_for_payment(self.app.db, payment_id))
                self.assertEqual(logs.records[0].getMessage(),
                                 "payment booking_id=42 outcome=not_refundable")

    def test_missing_payment(self):
        with self.assertLogs("spacey_payments", level="WARNING") as logs:
            response = self.refund(999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "payment not found"})
        self.assertEqual(logs.records[0].getMessage(),
                         "payment booking_id=None outcome=not_found")

    def test_invalid_body_or_reason_records_nothing(self):
        payment_id = self.seed_payment()
        for raw in ("null", "[]", '"text"', "true", "{broken"):
            with self.subTest(body=raw):
                response = self.refund(payment_id, data=raw, content_type="application/json")
                self.assertEqual(response.status_code, 400)
        for reason in (None, 123, True, [], {}, "", "  "):
            with self.subTest(reason=reason):
                with self.assertLogs("spacey_payments", level="WARNING"):
                    response = self.refund(payment_id, json={"reason": reason})
                self.assertEqual(response.status_code, 400)
        self.assertIsNone(repository.get_refund_for_payment(self.app.db, payment_id))

    def test_database_failures_are_sanitized(self):
        payment_id = self.seed_payment()
        for operation, booking_id in (("get_payment", None), ("insert_refund", 42)):
            with self.subTest(operation=operation):
                with patch.object(repository, operation, side_effect=psycopg.OperationalError(
                    "secret SQL parameters 4242424242424242"
                )), self.assertLogs("spacey_payments", level="ERROR") as logs:
                    response = self.refund(payment_id)
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.get_json(), {"error": "payment unavailable"})
                self.assertEqual([r.getMessage() for r in logs.records],
                                 [f"payment booking_id={booking_id} outcome=database_error"])
        self.assertIsNone(repository.get_refund_for_payment(self.app.db, payment_id))

    def test_concurrent_requests_create_one_refund(self):
        payment_id = self.seed_payment()
        other_app = create_app(reset_on_start=False)
        self.addCleanup(other_app.db.close)
        barrier = Barrier(2)
        insert_refund = repository.insert_refund

        def concurrent_insert(*args):
            barrier.wait(timeout=5)
            return insert_refund(*args)

        def request_refund(app):
            with app.test_client() as client:
                response = client.post(f"/payments/{payment_id}/refund")
                return response.status_code, response.get_json()

        with patch.object(repository, "insert_refund", side_effect=concurrent_insert):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(request_refund, (self.app, other_app)))
        self.assertEqual(sorted(code for code, _ in results), [200, 201])
        self.assertEqual(results[0][1], results[1][1])
        with self.app.db.cursor() as cur:
            cur.execute("SELECT count(*) AS count FROM payments WHERE status = 'refunded'")
            self.assertEqual(cur.fetchone()["count"], 1)
