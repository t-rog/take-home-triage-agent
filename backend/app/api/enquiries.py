"""The enquiry lifecycle: create, list, fetch, review, and retry. No business
logic lives here beyond request parsing and orchestration -- classification
lives in services/classifier.py, routing in services/router.py, and the
create/retry sequencing in services/pipeline.py."""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import func

from ..db import SessionLocal
from ..models import Enquiry, Status, Team
from ..schemas import EnquiryCreate, ReviewRequest
from ..serializers import error_response, serialize_enquiry
from ..services import pipeline, router

enquiries_bp = Blueprint("enquiries", __name__)


@enquiries_bp.post("/enquiries")
def create_enquiry():
    """Validate the intake form, then run the full classify -> route -> gate
    pipeline synchronously before responding -- the caller gets back the
    finished, classified enquiry, not a job id to poll (see README's
    "classification is synchronous" design note)."""
    try:
        payload = EnquiryCreate.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify(error_response("validation_error", str(e))), 400

    session = SessionLocal()
    try:
        enquiry = pipeline.process(payload, session)
        return jsonify(serialize_enquiry(enquiry)), 201
    finally:
        session.close()


@enquiries_bp.get("/enquiries")
def list_enquiries():
    """Filterable, paginated enquiry list for the Queue page.

    `counts_by_status` is deliberately computed over the *unfiltered* table
    (a separate query, ignoring `status`/`service_line`/etc.) so the UI's
    filter-tab counts stay stable no matter what the current filter is --
    only `total`/`page`/`total_pages` reflect the active filters.
    """
    session = SessionLocal()
    try:
        query = session.query(Enquiry)

        status = request.args.get("status")
        if status:
            query = query.filter(Enquiry.status == Status(status))
        service_line = request.args.get("service_line")
        if service_line:
            query = query.filter(Enquiry.service_line == service_line)
        complexity = request.args.get("complexity")
        if complexity:
            query = query.filter(Enquiry.complexity == complexity)
        urgency = request.args.get("urgency")
        if urgency:
            query = query.filter(Enquiry.urgency == urgency)
        team_id = request.args.get("team_id")
        if team_id:
            query = query.filter(Enquiry.team_id == int(team_id))
        q = request.args.get("q")
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Enquiry.company_name.ilike(like)) | (Enquiry.description.ilike(like))
            )

        total = query.count()

        page = max(1, request.args.get("page", 1, type=int))
        page_size = min(50, max(1, request.args.get("page_size", 10, type=int)))
        total_pages = max(1, -(-total // page_size))
        page = min(page, total_pages)

        enquiries = (
            query.order_by(Enquiry.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        counts_by_status = dict(
            session.query(Enquiry.status, func.count(Enquiry.id)).group_by(Enquiry.status).all()
        )
        counts_by_status = {k.value: v for k, v in counts_by_status.items()}

        return jsonify(
            {
                "enquiries": [serialize_enquiry(e) for e in enquiries],
                "counts_by_status": counts_by_status,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
        )
    finally:
        session.close()


@enquiries_bp.get("/enquiries/<int:enquiry_id>")
def get_enquiry(enquiry_id: int):
    """Fetch one enquiry by id. Not currently used by the frontend (the
    Queue page finds enquiries in its already-loaded list instead), kept for
    completeness and for direct API testing/debugging."""
    session = SessionLocal()
    try:
        enquiry = session.get(Enquiry, enquiry_id)
        if enquiry is None:
            return jsonify(error_response("not_found", "Enquiry not found")), 404
        return jsonify(serialize_enquiry(enquiry))
    finally:
        session.close()


@enquiries_bp.post("/enquiries/<int:enquiry_id>/review")
def review_enquiry(enquiry_id: int):
    """A human reviewer's decision on one enquiry. Three actions:

    - `close`: dismiss it (spam/out of scope) without touching its
      classification -- returns immediately, its own branch below.
    - `correct`: overwrite service_line/complexity/team_id in place (no
      history kept beyond the `was_corrected` flag). If a team isn't given
      explicitly but the classification changed, the enquiry is re-routed
      automatically so it never ends up pointed at a team that matched the
      old, pre-correction classification.
    - `approve`: no changes, just confirms the model's existing answer.

    All three end with `status='routed'` and `reviewed=True`.
    """
    try:
        payload = ReviewRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify(error_response("validation_error", str(e))), 400

    session = SessionLocal()
    try:
        enquiry = session.get(Enquiry, enquiry_id)
        if enquiry is None:
            return jsonify(error_response("not_found", "Enquiry not found")), 404

        enquiry.reviewed_by = payload.reviewer

        if payload.action == "close":
            enquiry.status = Status.closed
            enquiry.reviewed = True
            session.commit()
            return jsonify(serialize_enquiry(enquiry))

        if payload.action == "correct":
            changed = False
            service_line_changed = (
                payload.corrected_service_line is not None
                and payload.corrected_service_line != enquiry.service_line
            )
            complexity_changed = (
                payload.corrected_complexity is not None
                and payload.corrected_complexity != enquiry.complexity
            )
            if service_line_changed:
                enquiry.service_line = payload.corrected_service_line
                changed = True
            if complexity_changed:
                enquiry.complexity = payload.corrected_complexity
                changed = True

            if payload.corrected_team_id is not None:
                if payload.corrected_team_id != enquiry.team_id:
                    enquiry.team_id = payload.corrected_team_id
                    enquiry.matched_rule = None  # manual pick, not a rule match
                    enquiry.routed_at = datetime.now(timezone.utc)
                    changed = True
            elif service_line_changed or complexity_changed:
                # No team explicitly chosen, but the classification moved --
                # re-route so the enquiry doesn't stay pointed at a team that
                # matched the old, now-corrected classification.
                teams = session.query(Team).all()
                context = {
                    "service_line": enquiry.service_line,
                    "complexity": enquiry.complexity,
                    "urgency": enquiry.urgency,
                    "industry": enquiry.industry,
                }
                team, rule_name = router.route(context, teams)
                if team.id != enquiry.team_id or rule_name != enquiry.matched_rule:
                    enquiry.team_id = team.id
                    enquiry.matched_rule = rule_name
                    enquiry.routed_at = datetime.now(timezone.utc)
                    changed = True

            if changed:
                enquiry.was_corrected = True

        enquiry.status = Status.routed
        enquiry.reviewed = True
        session.commit()
        return jsonify(serialize_enquiry(enquiry))
    finally:
        session.close()


@enquiries_bp.post("/enquiries/<int:enquiry_id>/retry")
def retry_enquiry(enquiry_id: int):
    """Re-run the pipeline for a `failed` enquiry, updating it in place
    (same id, no new row). Rejects anything not currently `failed` -- this
    is a recovery path for classification failures, not a general
    reclassify-on-demand button."""
    session = SessionLocal()
    try:
        enquiry = session.get(Enquiry, enquiry_id)
        if enquiry is None:
            return jsonify(error_response("not_found", "Enquiry not found")), 404
        if enquiry.status != Status.failed:
            return (
                jsonify(error_response("invalid_state", "Only failed enquiries can be retried")),
                400,
            )
        enquiry = pipeline.reprocess(enquiry, session)
        return jsonify(serialize_enquiry(enquiry))
    finally:
        session.close()
