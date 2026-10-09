from tests.support import AppTestCase


class HealthTests(AppTestCase):
    def test_health_reports_ok_and_revision(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")
        self.assertIn("revision", resp.get_json())

    def test_health_is_503_and_logged_as_error_when_database_is_down(self):
        self.app.db.close()
        with self.assertLogs("spacey_payments", level="ERROR") as logs:
            resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(
            [r.getMessage() for r in logs.records],
            ["health outcome=database_unreachable"],
        )
