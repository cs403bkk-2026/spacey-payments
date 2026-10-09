import psycopg
from flask import Blueprint, current_app, jsonify

from src import config
from src.logger import logger

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    try:
        with current_app.db.cursor() as cur:
            cur.execute("SELECT 1")
    except psycopg.Error:
        logger.error("health outcome=database_unreachable")
        return jsonify(status="error", error="database unreachable"), 503
    return jsonify(status="ok", revision=config.APP_REVISION)
