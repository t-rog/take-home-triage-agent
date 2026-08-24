"""Read-only lookup data for frontend dropdowns -- teams and service lines.
Nothing here is ever created or edited through the API; both are seeded."""

from flask import Blueprint, jsonify

from ..db import SessionLocal
from ..domain import SERVICE_LINE_DESCRIPTIONS
from ..models import Team
from ..serializers import serialize_team

reference_bp = Blueprint("reference", __name__)


@reference_bp.get("/teams")
def list_teams():
    """All teams, including the default catch-all, for the correction
    dropdown and the service-line filter's team context."""
    session = SessionLocal()
    try:
        teams = session.query(Team).order_by(Team.id).all()
        return jsonify([serialize_team(t) for t in teams])
    finally:
        session.close()


@reference_bp.get("/service-lines")
def list_service_lines():
    """Every service line plus its human-readable description, for the
    Queue page's filter dropdown and correction controls. No DB query --
    this is domain.py's static dict, not a table."""
    return jsonify(
        [
            {"value": sl.value, "description": desc}
            for sl, desc in SERVICE_LINE_DESCRIPTIONS.items()
        ]
    )
