from flask import Flask

from src import config, db
from src.health import bp as health_bp
from src.logger import logger
from src.payments import repository
from src.payments.api import bp as payments_bp


def create_app(
        database_url: str = config.DATABASE_URL, reset_on_start: bool | None = None
) -> Flask:
    if reset_on_start is None:
        reset_on_start = config.reset_db_on_start()

    app = Flask(__name__)
    app.db = db.get_connection(database_url)
    if reset_on_start:
        logger.warning("startup reset_on_start=true tables truncated")
        repository.reset_tables(app.db)
    logger.info("startup revision=%s", config.APP_REVISION)

    app.register_blueprint(health_bp)
    app.register_blueprint(payments_bp)
    return app
