"""Postgres (src/database.py): the shared engine and session factory."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from src.database import Postgres
from src.app import migrate_database
from src.database import MIGRATIONS_DIR
from tests.support import UNREACHABLE_DATABASE_URL, unreachable_database


class PostgresTests(unittest.TestCase):
    def setUp(self):
        saved = Postgres._instance
        self.addCleanup(setattr, Postgres, "_instance", saved)
        Postgres._instance = None

    def test_get_initialises_once_and_reuses_the_instance(self):
        first = Postgres.get()
        self.addCleanup(first.close)
        self.assertIs(Postgres.get(), first)

    def test_init_reads_database_url_from_the_environment(self):
        with mock.patch.dict(os.environ, {Postgres.URL_KEY: UNREACHABLE_DATABASE_URL}):
            Postgres.init()
        self.addCleanup(Postgres.get().close)
        self.assertEqual(Postgres.get()._database_url, UNREACHABLE_DATABASE_URL)

    def test_init_falls_back_to_the_local_url(self):
        env = {k: v for k, v in os.environ.items() if k != Postgres.URL_KEY}
        with mock.patch.dict(os.environ, env, clear=True):
            Postgres.init()
        self.addCleanup(Postgres.get().close)
        self.assertEqual(Postgres.get()._database_url, Postgres.LOCAL_URL)

    def test_session_executes_queries(self):
        self.addCleanup(lambda: Postgres.get().close())
        with Postgres.get().get_session() as session:
            self.assertEqual(session.execute(text("SELECT 1")).scalar(), 1)

    def test_session_rolls_back_and_reraises_on_error(self):
        self.addCleanup(lambda: Postgres.get().close())
        with mock.patch("sqlalchemy.orm.Session.rollback") as rollback:
            with self.assertRaises(ValueError):
                with Postgres.get().get_session():
                    raise ValueError("boom")
        rollback.assert_called_once()

    def test_unreachable_database_fails_on_use_not_on_init(self):
        Postgres.init()
        with unreachable_database():
            with Postgres.get().get_session() as session:
                with self.assertRaises(Exception):
                    session.execute(text("SELECT 1"))


class MigrationTests(unittest.TestCase):
    def setUp(self):
        Postgres.init()
        self.addCleanup(lambda: Postgres.get().close())
        self.postgres = Postgres.get()

    def scratch_migrations(self, files: dict[str, str]) -> Path:
        directory = Path(tempfile.mkdtemp())
        for name, sql in files.items():
            (directory / name).write_text(sql)
        self.addCleanup(self.drop, files)
        return directory

    def drop(self, files: dict[str, str]) -> None:
        with self.postgres.get_session() as session:
            session.execute(text("DROP TABLE IF EXISTS migration_probe"))
            session.execute(text("DELETE FROM schema_migrations WHERE name = ANY(:names)"),
                            {"names": list(files)})
            session.commit()

    def test_every_repo_migration_is_recorded(self):
        self.postgres.migrate()
        with self.postgres.get_session() as session:
            applied = set(session.scalars(text("SELECT name FROM schema_migrations")))
        self.assertTrue({p.name for p in MIGRATIONS_DIR.glob("*.sql")} <= applied)

    def test_migrations_apply_once_in_filename_order(self):
        directory = self.scratch_migrations({
            "zz_probe_2.sql": "INSERT INTO migration_probe VALUES (2);",
            "zz_probe_1.sql": "CREATE TABLE migration_probe (n INTEGER);",
        })

        self.assertEqual(self.postgres.migrate(directory), ["zz_probe_1.sql", "zz_probe_2.sql"])
        self.assertEqual(self.postgres.migrate(directory), [])
        with self.postgres.get_session() as session:
            rows = list(session.scalars(text("SELECT n FROM migration_probe")))
        self.assertEqual(rows, [2])

    def test_a_failing_migration_is_not_recorded(self):
        directory = self.scratch_migrations({"zz_probe_1.sql": "NOT SQL;"})
        with self.assertRaises(ProgrammingError):
            self.postgres.migrate(directory)
        self.assertEqual(self.postgres.migrate(self.scratch_migrations({})), [])
        with self.postgres.get_session() as session:
            recorded = session.scalar(text(
                "SELECT count(*) FROM schema_migrations WHERE name = 'zz_probe_1.sql'"))
        self.assertEqual(recorded, 0)


class StartupFailureTests(unittest.TestCase):
    def test_unreachable_database_exits_without_disclosing_credentials(self):
        Postgres.init()
        with unreachable_database():
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                with self.assertRaises(SystemExit) as failure:
                    migrate_database()

        message = str(failure.exception)
        self.assertIn("Could not connect to the database", message)
        for secret in (UNREACHABLE_DATABASE_URL, "private-password"):
            self.assertNotIn(secret, message)
            self.assertNotIn(secret, "\n".join(logs.output))
        self.assertEqual([r.getMessage() for r in logs.records],
                         ["startup outcome=database_unreachable"])
        self.assertTrue(failure.exception.__suppress_context__)

    def test_broken_migration_exits_with_its_own_message(self):
        error = ProgrammingError("SELECT", {}, Exception("syntax error"))
        with mock.patch.object(Postgres, "migrate", side_effect=error):
            with self.assertLogs("spacey_payments", level="ERROR") as logs:
                with self.assertRaises(SystemExit) as failure:
                    migrate_database()
        self.assertEqual(str(failure.exception), "Could not apply the database migrations.")
        self.assertEqual([r.getMessage() for r in logs.records],
                         ["startup outcome=migration_failed"])
