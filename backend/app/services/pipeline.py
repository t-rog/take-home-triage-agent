"""Orchestrates one enquiry through classify -> route -> gate -> persist.
The only module that calls both classifier.classify() and router.route(),
so this is where their outputs get combined into a status and a saved row."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Enquiry, Status, Team
from ..schemas import EnquiryCreate
from . import router
from .classifier import ClassificationError, ClassificationResult, classify


def _needs_review(result: ClassificationResult) -> bool:
    """Should a confident-looking classification still go to a human? Yes if
    any of: confidence is below CONFIDENCE_THRESHOLD, the model raised any
    flag (e.g. spam, insufficient_information), or the runner-up service
    line's confidence is within 0.15 of the top pick (a close second guess
    is itself a signal the model isn't sure). Any one of these alone is
    enough -- they're not combined into a score."""
    if result.confidence < settings.CONFIDENCE_THRESHOLD:
        return True
    if result.flags:
        return True
    if (
        result.runner_up_confidence is not None
        and (result.confidence - result.runner_up_confidence) <= 0.15
    ):
        return True
    return False


def process(payload: EnquiryCreate, session: Session) -> Enquiry:
    """Classify, route, gate, and persist one enquiry. Runs synchronously —
    at 40-60 enquiries/week there is no throughput problem a queue would
    solve, and a failed call must still leave a visible row."""
    try:
        result = classify(payload)
    except ClassificationError as e:
        enquiry = Enquiry(
            contact_name=payload.contact_name,
            contact_email=payload.contact_email,
            company_name=payload.company_name,
            industry=payload.industry,
            industry_other=payload.industry_other,
            company_size=payload.company_size,
            urgency=payload.urgency,
            description=payload.description,
            status=Status.failed,
            error_message=e.message,
        )
        session.add(enquiry)
        session.commit()
        return enquiry

    teams = session.query(Team).all()
    context = {
        "service_line": result.service_line,
        "complexity": result.complexity,
        "urgency": payload.urgency,
        "industry": payload.industry,
    }
    team, rule_name = router.route(context, teams)
    status = Status.needs_review if _needs_review(result) else Status.routed

    enquiry = Enquiry(
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        company_name=payload.company_name,
        industry=payload.industry,
        industry_other=payload.industry_other,
        company_size=payload.company_size,
        urgency=payload.urgency,
        description=payload.description,
        service_line=result.service_line,
        complexity=result.complexity,
        confidence=result.confidence,
        rationale=result.rationale,
        runner_up_service_line=result.runner_up_service_line,
        runner_up_confidence=result.runner_up_confidence,
        key_signals=result.key_signals,
        flags=[f.value for f in result.flags],
        status=status,
        team_id=team.id,
        matched_rule=rule_name,
        routed_at=datetime.now(timezone.utc),
    )
    session.add(enquiry)
    session.commit()
    return enquiry


def reprocess(enquiry: Enquiry, session: Session) -> Enquiry:
    """Retry: rebuilds the original form submission from the stored row,
    re-runs classify -> route -> gate against it, and overwrites the same
    row's classification/routing fields in place (no new row, unlike
    process()). Used by the `/retry` endpoint, which only allows this on
    enquiries currently `status='failed'`."""
    payload = EnquiryCreate(
        contact_name=enquiry.contact_name,
        contact_email=enquiry.contact_email,
        company_name=enquiry.company_name,
        industry=enquiry.industry,
        industry_other=enquiry.industry_other,
        company_size=enquiry.company_size,
        urgency=enquiry.urgency,
        description=enquiry.description,
    )
    try:
        result = classify(payload)
    except ClassificationError as e:
        enquiry.status = Status.failed
        enquiry.error_message = e.message
        session.commit()
        return enquiry

    teams = session.query(Team).all()
    context = {
        "service_line": result.service_line,
        "complexity": result.complexity,
        "urgency": payload.urgency,
        "industry": payload.industry,
    }
    team, rule_name = router.route(context, teams)

    enquiry.service_line = result.service_line
    enquiry.complexity = result.complexity
    enquiry.confidence = result.confidence
    enquiry.rationale = result.rationale
    enquiry.runner_up_service_line = result.runner_up_service_line
    enquiry.runner_up_confidence = result.runner_up_confidence
    enquiry.key_signals = result.key_signals
    enquiry.flags = [f.value for f in result.flags]
    enquiry.status = Status.needs_review if _needs_review(result) else Status.routed
    enquiry.team_id = team.id
    enquiry.matched_rule = rule_name
    enquiry.routed_at = datetime.now(timezone.utc)
    enquiry.error_message = None
    session.commit()
    return enquiry
