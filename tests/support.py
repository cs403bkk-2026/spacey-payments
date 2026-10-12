"""Shared test helpers. Tests need PostgreSQL at DATABASE_URL and wipe its
payments table, so point it at a disposable database."""

import unittest
from os import environ

import psycopg
from psycopg.rows import dict_row

from src.app import create_app
from src.database import Postgres
from src.repositories.payments import PaymentsRepository


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(reset_on_start=True)
        self.client = self.app.test_client()
        self.addCleanup(Postgres.get().close)
        self.db = psycopg.connect(environ["DATABASE_URL"], row_factory=dict_row, autocommit=True)
        self.addCleanup(self.db.close)
        self.session = Postgres.get()._session_factory()
        self.addCleanup(self.session.close)
        self.repository = PaymentsRepository(self.session)
