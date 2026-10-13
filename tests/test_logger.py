import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent


class LoggerTests(unittest.TestCase):
    def test_level_comes_from_log_level_and_defaults_to_info(self):
        code = (
            "from src.logger import logger; "
            "logger.debug('payment booking_id=7 outcome=started'); "
            "logger.info('payment booking_id=7 outcome=succeeded')"
        )
        for level in (None, "DEBUG", "debug", "WARNING"):
            with self.subTest(level=level):
                env = dict(os.environ)
                env.pop("LOG_LEVEL", None)
                if level:
                    env["LOG_LEVEL"] = level
                result = subprocess.run(
                    [sys.executable, "-c", code], env=env, cwd=ROOT,
                    capture_output=True, text=True, check=True)
                expected = "INFO payment booking_id=7 outcome=succeeded\n"
                if level and level.upper() == "DEBUG":
                    expected = "DEBUG payment booking_id=7 outcome=started\n" + expected
                if level == "WARNING":
                    expected = ""
                self.assertEqual(result.stderr, expected)
