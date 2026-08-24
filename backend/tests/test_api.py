"""Requires a reachable Postgres at DATABASE_URL. Point it at a disposable
database before running these tests -- they drop and recreate all tables."""

import pytest

from app import create_app
from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, ServiceLine, Team
from app.services import pipeline
from app.services.classifier import ClassificationResult

VALID_PAYLOAD = {
    "contact_name": "A Contact",
    "contact_email": "a@example.com",
    "company_name": "Acme",
    "industry": "technology",
    "company_size": "size_1_50",
    "urgency": "within_month",
    "description": "x" * 45,
}


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe and recreate every table before each test, and clear the scoped
    session after -- runs automatically for every test in this file, which
    is exactly why this file must never be pointed at a database with data
    worth keeping."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    SessionLocal.remove()


@pytest.fixture()
def client(monkeypatch):
    """A Flask test client on a freshly created app. Forces
    SEED_ON_START off regardless of the environment so tests get a
    genuinely empty database, not whatever seed.py would insert."""
    # Tests want a clean slate regardless of the environment's SEED_ON_START.
    monkeypatch.setattr(settings, "SEED_ON_START", False)
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.fixture()
def seeded_teams():
    """Three teams (two named service lines plus a default) -- enough to
    exercise routing and the review-correction team-cascade behavior
    without needing the full seed.py dataset."""
    session = SessionLocal()
    session.add_all(
        [
            Team(
                name="Data Team",
                service_line=ServiceLine.data_analytics,
                lead_name="L",
                lead_email="l@example.com",
                is_default=False,
            ),
            Team(
                name="Risk Team",
                service_line=ServiceLine.risk_compliance,
                lead_name="R",
                lead_email="r@example.com",
                is_default=False,
            ),
            Team(
                name="Intake Desk",
                service_line=None,
                lead_name="L2",
                lead_email="l2@example.com",
                is_default=True,
            ),
        ]
    )
    session.commit()
    session.close()


def _fake_result(**overrides):
    """A default-confident ClassificationResult, with any field overridable
    -- lets each test monkeypatch `pipeline.classify` to return a specific
    scenario (low confidence, a particular service line, ...) without a
    real API call."""
    base = dict(
        service_line=ServiceLine.data_analytics,
        complexity=None,
        confidence=0.9,
        rationale="test rationale",
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=[],
        flags=[],
        input_tokens=10,
        output_tokens=10,
        latency_ms=100,
    )
    base.update(overrides)
    return ClassificationResult(**base)


def test_health(client):
    """/api/health should report ok with a working database."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_create_enquiry_routes_when_confident(client, seeded_teams, monkeypatch):
    """A high-confidence classification (the default from _fake_result)
    should route straight through -- status='routed', team matching the
    classified service line -- without a review step."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result())
    resp = client.post("/api/enquiries", json=VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "routed"
    assert body["team"]["service_line"] == "data_analytics"


def test_create_enquiry_needs_review_on_low_confidence(client, seeded_teams, monkeypatch):
    """A confidence below CONFIDENCE_THRESHOLD should gate the enquiry to
    needs_review even though routing itself still succeeds."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result(confidence=0.4))
    resp = client.post("/api/enquiries", json=VALID_PAYLOAD)
    assert resp.get_json()["status"] == "needs_review"


def test_create_enquiry_rejects_short_description(client, seeded_teams):
    """The 40-character floor on description is enforced server-side, not
    just in the frontend form."""
    resp = client.post("/api/enquiries", json={**VALID_PAYLOAD, "description": "too short"})
    assert resp.status_code == 400


def test_list_enquiries_reports_counts_by_status(client, seeded_teams, monkeypatch):
    """The list response should include total/page/total_pages alongside
    the enquiries themselves, correct for a single-page result."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result())
    client.post("/api/enquiries", json=VALID_PAYLOAD)
    resp = client.get("/api/enquiries")
    body = resp.get_json()
    assert body["counts_by_status"]["routed"] == 1
    assert len(body["enquiries"]) == 1
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["total_pages"] == 1


def test_list_enquiries_paginates(client, seeded_teams, monkeypatch):
    """With 3 rows and page_size=2, page 1 should return 2 rows and page 2
    should return the remaining 1, with total/total_pages computed correctly."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result())
    for _ in range(3):
        client.post("/api/enquiries", json=VALID_PAYLOAD)

    resp = client.get("/api/enquiries?page_size=2&page=1")
    body = resp.get_json()
    assert len(body["enquiries"]) == 2
    assert body["total"] == 3
    assert body["total_pages"] == 2

    resp2 = client.get("/api/enquiries?page_size=2&page=2")
    assert len(resp2.get_json()["enquiries"]) == 1


def test_review_close_dismisses_without_touching_classification(client, seeded_teams, monkeypatch):
    """A `close` action should set status='closed' and reviewed=True, but
    leave service_line/complexity exactly as the model left them --
    dismissing an enquiry isn't the same as correcting it."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result(confidence=0.4))
    created = client.post("/api/enquiries", json=VALID_PAYLOAD).get_json()

    resp = client.post(
        f"/api/enquiries/{created['id']}/review",
        json={"reviewer": "Analyst", "action": "close"},
    )
    body = resp.get_json()
    assert body["status"] == "closed"
    assert body["reviewed"] is True
    assert body["reviewed_by"] == "Analyst"
    assert body["was_corrected"] is False
    assert body["service_line"] == created["service_line"]


def test_review_correct_sets_was_corrected_and_routes(client, seeded_teams, monkeypatch):
    """Correcting just the complexity (no service line or team change)
    should flip was_corrected and move the enquiry to routed."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result(confidence=0.4))
    created = client.post("/api/enquiries", json=VALID_PAYLOAD).get_json()
    assert created["status"] == "needs_review"

    resp = client.post(
        f"/api/enquiries/{created['id']}/review",
        json={"reviewer": "Analyst", "action": "correct", "corrected_complexity": "complex"},
    )
    body = resp.get_json()
    assert body["status"] == "routed"
    assert body["was_corrected"] is True
    assert body["reviewed_by"] == "Analyst"
    assert body["complexity"] == "complex"


def test_review_correct_without_team_id_reroutes_to_match_new_service_line(
    client, seeded_teams, monkeypatch
):
    """Regression test for a real bug: correcting service_line without also
    specifying corrected_team_id must re-route automatically, not leave the
    enquiry pointed at the team that matched its old classification."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result(confidence=0.4))
    created = client.post("/api/enquiries", json=VALID_PAYLOAD).get_json()
    assert created["team"]["service_line"] == "data_analytics"

    resp = client.post(
        f"/api/enquiries/{created['id']}/review",
        json={
            "reviewer": "Analyst",
            "action": "correct",
            "corrected_service_line": "risk_compliance",
        },
    )
    body = resp.get_json()
    assert body["service_line"] == "risk_compliance"
    # No corrected_team_id was given, so the enquiry must not be left pointed
    # at the old team that matched the pre-correction service line.
    assert body["team"]["service_line"] == "risk_compliance"
    assert body["was_corrected"] is True


def test_review_approve_does_not_set_was_corrected(client, seeded_teams, monkeypatch):
    """Approving a needs_review enquiry should route it without flipping
    was_corrected -- confirming the model's answer isn't a correction."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result(confidence=0.4))
    created = client.post("/api/enquiries", json=VALID_PAYLOAD).get_json()

    resp = client.post(
        f"/api/enquiries/{created['id']}/review",
        json={"reviewer": "Analyst", "action": "approve"},
    )
    body = resp.get_json()
    assert body["status"] == "routed"
    assert body["was_corrected"] is False
    assert body["reviewed"] is True
    assert body["reviewed_by"] == "Analyst"


def test_retry_only_allowed_on_failed_enquiries(client, seeded_teams, monkeypatch):
    """/retry should reject an enquiry that isn't currently status='failed'
    -- it's a recovery path, not a general reclassify button."""
    monkeypatch.setattr(pipeline, "classify", lambda payload: _fake_result())
    created = client.post("/api/enquiries", json=VALID_PAYLOAD).get_json()

    resp = client.post(f"/api/enquiries/{created['id']}/retry")
    assert resp.status_code == 400
