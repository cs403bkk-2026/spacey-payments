"""Environment-driven settings. Every variable has a development-only default;
a real deployment should set them all explicitly."""

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://spacey:spacey@localhost:5432/spacey"
)
APP_REVISION = os.getenv("APP_REVISION", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def reset_db_on_start() -> bool:
    """Truncates tables on start. Disposable local or test data only."""
    return os.getenv("RESET_DB_ON_START", "false").lower() == "true"
