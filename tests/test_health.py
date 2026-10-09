from tests.support import AppTestCase


class HealthTests(AppTestCase):
    def test_health_reports_ok_and_revision(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")
        self.assertIn("revision", resp.get_json())
