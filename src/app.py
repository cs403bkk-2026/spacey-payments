from typing import Optional

from flask import Flask

from src.config import (
    APP_NAME,
    APP_REVISION,
    RESET_DB_ON_START
)
from src.database import Postgres
from src.logger import logger
from src.routes import health_blueprint, payment_blueprint
from src.unit_of_work import UnitOfWork


def reset_database(reset: Optional[bool] = None) -> None:
    if reset is None:
        reset = RESET_DB_ON_START

    if not reset:
        return

    with UnitOfWork().transaction() as services:
        if (result := services.payments.repository.truncate()).failed:
            logger.error("Could not reset table because %s", result.reason)

        logger.info("startup reset_on_start=true tables truncated")


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_blueprint)
    app.register_blueprint(payment_blueprint)


def create_app(reset_on_start: Optional[bool] = None) -> Flask:
    Postgres.init()
    reset_database(reset_on_start)

    app: Flask = Flask(APP_NAME)
    register_blueprints(app)

    logger.info("startup revision=%s", APP_REVISION)
    return app
