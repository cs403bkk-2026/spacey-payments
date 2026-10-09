"""Shared test helpers. Tests need PostgreSQL at DATABASE_URL and wipe its
payments table, so point it at a disposable database."""

import unittest

from src.app import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(reset_on_start=True)
        self.client = self.app.test_client()
        self.addCleanup(self.app.db.close)
