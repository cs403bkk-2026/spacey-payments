"""Environment-driven settings. Every variable has a development-only default;
a real deployment should set them all explicitly."""

from os import getenv

# Env
APP_REVISION: str = getenv("APP_REVISION", "local")
LOG_LEVEL: str = getenv("LOG_LEVEL", "INFO").upper()
RESET_DB_ON_START: bool = getenv("RESET_DB_ON_START", "false").lower() == "true"
# Shared secret Purchase sends in X-Service-Token. No default: while it is unset
# every endpoint except /health answers 401.
SERVICE_TOKEN: str = getenv("SERVICE_TOKEN", "")

# Constants
APP_NAME: str = "SpacyPayments"
