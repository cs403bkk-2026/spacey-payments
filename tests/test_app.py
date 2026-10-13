"""create_app (src/app.py): startup reset and logging."""

from unittest import mock

from sqlalchemy import text

from src import config
from src.app import create_app
from src.repositories.payments import PaymentsRepository
from src.result import Result
from src.unit_of_work import UnitOfWork
from tests.support import DatabaseTestCase


class CreateAppTests(DatabaseTestCase):
    def test_reset_on_start_truncates_payments(self):
        self.insert_payment()
        with self.assertLogs("spacey_payments", level="INFO") as logs:
            create_app(reset_on_start=True)
        self.assertEqual(self.count_payments(), 0)
        self.assertIn("startup reset_on_start=true tables truncated",
                      [r.getMessage() for r in logs.records])

    def test_without_reset_payments_are_kept(self):
        self.insert_payment()
        create_app(reset_on_start=False)
        self.assertEqual(self.count_payments(), 1)

    def test_reset_defaults_to_the_environment_setting(self):
        self.insert_payment()
        with mock.patch("src.app.RESET_DB_ON_START", False):
            create_app()
        self.assertEqual(self.count_payments(), 1)

    def test_failed_reset_is_logged_without_database_details(self):
        failure = Result.failure("relation payments does not exist; SQL: TRUNCATE ...")
        with mock.patch.object(PaymentsRepository, "truncate", return_value=failure):
            with self.assertLogs("spacey_payments", level="INFO") as logs:
                create_app(reset_on_start=True)

        messages = [(r.levelname, r.getMessage()) for r in logs.records]
        self.assertIn(("ERROR", "startup reset_on_start=true outcome=database_error"), messages)
        self.assertNotIn("startup reset_on_start=true tables truncated", [m for _, m in messages])
        self.assertNotIn("relation payments", "\n".join(logs.output))

    def test_startup_logs_the_revision(self):
        with self.assertLogs("spacey_payments", level="INFO") as logs:
            create_app(reset_on_start=False)
        self.assertIn(f"startup revision={config.APP_REVISION}",
                      [r.getMessage() for r in logs.records])

    def test_startup_applies_migrations(self):
        with UnitOfWork().transaction() as services:
            applied = set(services.session.scalars(text("SELECT name FROM schema_migrations")))
        self.assertIn("003_add_payment_unique_indexes.sql", applied)

    def test_startup_warns_when_the_service_token_is_unset(self):
        with mock.patch.object(config, "SERVICE_TOKEN", ""):
            with self.assertLogs("spacey_payments", level="WARNING") as logs:
                create_app(reset_on_start=False)
        self.assertEqual([r.getMessage() for r in logs.records],
                         ["startup service_token=unset payment endpoints answer 401"])
