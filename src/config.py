"""Environment-driven settings. Every variable has a development-only default;
a real deployment should set them all explicitly."""

from os import getenv

# Env
APP_REVISION: str = getenv("APP_REVISION", "local")
LOG_LEVEL: str = getenv("LOG_LEVEL", "INFO").upper()
RESET_DB_ON_START: bool = getenv("RESET_DB_ON_START", "false").lower() == "true"

# Constants
APP_NAME: str = "SpacyPayments"
