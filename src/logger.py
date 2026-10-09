"""The service's single logger. Every module imports this one instance:
    from src.logger import logger
Level comes from LOG_LEVEL (default INFO); output goes to stderr.
Log booking ids and fixed outcomes only - never card data, and never database
exception text (it can include SQL parameters)."""

import logging

from src import config

logger = logging.getLogger("spacey_payments")
if not logger.handlers:
    logger.setLevel(config.LOG_LEVEL)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
