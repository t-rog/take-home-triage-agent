"""Hand-written JSON shapes for API responses -- the mirror image of
schemas.py, which validates requests. Kept as plain functions rather than
Pydantic response models since these are simple, one-directional mappings
from SQLAlchemy objects to dicts."""

from .models import Enquiry, Team


def error_response(code: str, message: str) -> dict:
    """The standard `{"error": {...}}` envelope every non-2xx response uses."""
    return {"error": {"code": code, "message": message}}


def serialize_team(team: Team) -> dict:
    """Team -> API JSON, including the lead's name/email so a client is
    never routed to an anonymous team bucket."""
    return {
        "id": team.id,
        "name": team.name,
        "service_line": team.service_line.value if team.service_line else None,
        "lead_name": team.lead_name,
        "lead_email": team.lead_email,
        "is_default": team.is_default,
    }


def serialize_enquiry(enquiry: Enquiry) -> dict:
    """Enquiry -> API JSON. Enum columns are unwrapped to their `.value`
    string, nullable numeric/enum fields are None-checked explicitly (rather
    than relying on truthiness, since 0.0 confidence is a valid value), and
    the related team is nested via serialize_team rather than just its id."""
    return {
        "id": enquiry.id,
        "submitted_at": enquiry.submitted_at.isoformat(),
        "contact_name": enquiry.contact_name,
        "contact_email": enquiry.contact_email,
        "company_name": enquiry.company_name,
        "industry": enquiry.industry.value,
        "industry_other": enquiry.industry_other,
        "company_size": enquiry.company_size.value,
        "urgency": enquiry.urgency.value,
        "description": enquiry.description,
        "service_line": enquiry.service_line.value if enquiry.service_line else None,
        "complexity": enquiry.complexity.value if enquiry.complexity else None,
        "confidence": float(enquiry.confidence) if enquiry.confidence is not None else None,
        "rationale": enquiry.rationale,
        "runner_up_service_line": (
            enquiry.runner_up_service_line.value if enquiry.runner_up_service_line else None
        ),
        "runner_up_confidence": (
            float(enquiry.runner_up_confidence)
            if enquiry.runner_up_confidence is not None
            else None
        ),
        "key_signals": enquiry.key_signals or [],
        "flags": enquiry.flags or [],
        "status": enquiry.status.value,
        "team": serialize_team(enquiry.team) if enquiry.team else None,
        "matched_rule": enquiry.matched_rule,
        "routed_at": enquiry.routed_at.isoformat() if enquiry.routed_at else None,
        "error_message": enquiry.error_message,
        "reviewed": enquiry.reviewed,
        "reviewed_by": enquiry.reviewed_by,
        "was_corrected": enquiry.was_corrected,
        "created_at": enquiry.created_at.isoformat(),
        "updated_at": enquiry.updated_at.isoformat(),
    }
