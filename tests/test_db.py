import unittest
from unittest import mock

from sqlalchemy.exc import OperationalError

from src.database import Postgres


class ConnectionFailureTests(unittest.TestCase):
    def test_connection_failure_does_not_disclose_credentials(self):
        database_url = "postgresql://example:private-password@db/payments"
        error = OperationalError("connect", {}, Exception(f"Rejected connection: {database_url}"))

        with mock.patch("src.database.run_migrations", side_effect=error):
            with self.assertLogs("spacey_payments", level="ERROR"):
                with self.assertRaises(SystemExit) as failure:
                    Postgres.init()

        message = str(failure.exception)
        self.assertIn("Could not connect to the database", message)
        self.assertNotIn(database_url, message)
        self.assertNotIn("private-password", message)
        self.assertTrue(failure.exception.__suppress_context__)
