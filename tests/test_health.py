from src import config
from tests.support import DatabaseTestCase, UNREACHABLE_DATABASE_URL, unreachable_database


class HealthTests(DatabaseTestCase):
    def test_health_reports_ok_and_revision(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "ok", "revision": config.APP_REVISION})

    def test_health_is_503_and_logged_as_error_when_database_is_down(self):
        with unreachable_database():
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                resp = self.client.get("/health")

        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json(), {"status": "error", "error": "database unreachable"})
        self.assertEqual(
            [r.getMessage() for r in logs.records],
            ["health outcome=database_unreachable"],
        )

    def test_database_failure_does_not_disclose_connection_details(self):
        with unreachable_database():
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                resp = self.client.get("/health")

        exposed = resp.get_data(as_text=True) + "\n".join(logs.output)
        for secret in (UNREACHABLE_DATABASE_URL, "private-password", "127.0.0.1"):
            self.assertNotIn(secret, exposed)

    def test_health_recovers_when_database_comes_back(self):
        with unreachable_database():
            with self.assertLogs("spacey_payments", level="ERROR"):
                self.client.get("/health")
        self.assertEqual(self.client.get("/health").status_code, 200)
