"""Flask application factory."""

from flask import Flask, jsonify
from sqlalchemy import text

from .api.enquiries import enquiries_bp
from .api.reference import reference_bp
from .config import settings
from .db import engine
from .models import Base
from .seed import seed_if_needed


def create_app() -> Flask:
    """Build and configure the Flask app: create tables if they don't exist
    (no Alembic -- see PROJECT_PLAN.md), seed demo data if configured,
    register the two blueprints, and add a `/api/health` check."""
    app = Flask(__name__)

    Base.metadata.create_all(engine)
    if settings.SEED_ON_START:
        seed_if_needed()

    app.register_blueprint(enquiries_bp, url_prefix="/api")
    app.register_blueprint(reference_bp, url_prefix="/api")

    @app.get("/api/health")
    def health():
        """Reports real DB connectivity (runs `SELECT 1`), not just that the
        process is up -- used by the frontend and by anyone checking whether
        `docker compose up` finished successfully."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok})

    return app
