from flask import Blueprint, jsonify

from src import config
from src.logger import logger
from src.unit_of_work import UnitOfWork

health_blueprint: Blueprint = Blueprint("health", __name__)


@health_blueprint.get("/health")
def health():
    with UnitOfWork().transaction() as services:
        if (result := services.health.check()).failed:
            # result.reason is database exception text: never log or return it
            logger.error("health outcome=database_unreachable")
            return jsonify(status="error", error="database unreachable"), 503

    return jsonify(status="ok", revision=config.APP_REVISION)
