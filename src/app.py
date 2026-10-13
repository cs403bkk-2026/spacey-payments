from typing import Optional

from flask import Flask
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from src import config
from src.config import (
    APP_NAME,
    APP_REVISION,
    RESET_DB_ON_START
)
from src.database import Postgres
from src.logger import logger
from src.routes import health_blueprint, payment_blueprint
from src.unit_of_work import UnitOfWork


def migrate_database() -> None:
    try:
        applied: list[str] = Postgres.get().migrate()

    # The driver's message can carry connection details; never print it.
    except OperationalError:
        logger.error("startup outcome=database_unreachable")
        raise SystemExit(
            "Could not connect to the database (check DATABASE_URL).\n"
            "Is Postgres running? Try: docker compose up db -d"
        ) from None

    except SQLAlchemyError:
        logger.error("startup outcome=migration_failed")
        raise SystemExit("Could not apply the database migrations.") from None

    for name in applied:
        logger.info("migration applied name=%s", name)


def reset_database(reset: Optional[bool] = None) -> None:
    if reset is None:
        reset = RESET_DB_ON_START

    if not reset:
        return

    with UnitOfWork().transaction() as services:
        if services.payments.repository.truncate().failed:
            logger.error("startup reset_on_start=true outcome=database_error")
            return

        logger.info("startup reset_on_start=true tables truncated")


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_blueprint)
    app.register_blueprint(payment_blueprint)


def create_app(reset_on_start: Optional[bool] = None) -> Flask:
    Postgres.init()
    migrate_database()
    reset_database(reset_on_start)

    app: Flask = Flask(APP_NAME)
    register_blueprints(app)

    if not config.SERVICE_TOKEN:
        logger.warning("startup service_token=unset payment endpoints answer 401")
    logger.info("startup revision=%s", APP_REVISION)
    return app
