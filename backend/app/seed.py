"""Idempotent seed data. Sample enquiries are inserted pre-classified (hand
-written results, not a live model call) so `docker compose up` produces a
populated queue with no API key required."""

from datetime import datetime, timezone

from .db import SessionLocal
from .models import CompanySize, Complexity, Enquiry, Flag, Industry, ServiceLine, Status, Team, Urgency

# One team per service line, plus a 7th "Intake Desk" catch-all with
# service_line=None and is_default=True -- see router.route()'s fallback.
TEAMS = [
    {
        "name": "Insight & Analytics Team",
        "service_line": ServiceLine.data_analytics,
        "lead_name": "Priya Nathan",
        "lead_email": "priya.nathan@example.com",
        "is_default": False,
    },
    {
        "name": "Risk & Compliance Team",
        "service_line": ServiceLine.risk_compliance,
        "lead_name": "Marcus Webb",
        "lead_email": "marcus.webb@example.com",
        "is_default": False,
    },
    {
        "name": "Operations Advisory Team",
        "service_line": ServiceLine.operations,
        "lead_name": "Dana Alcorn",
        "lead_email": "dana.alcorn@example.com",
        "is_default": False,
    },
    {
        "name": "Technology Transformation Team",
        "service_line": ServiceLine.technology_transformation,
        "lead_name": "Felix Okoro",
        "lead_email": "felix.okoro@example.com",
        "is_default": False,
    },
    {
        "name": "People & Change Team",
        "service_line": ServiceLine.people_change,
        "lead_name": "Greta Lindqvist",
        "lead_email": "greta.lindqvist@example.com",
        "is_default": False,
    },
    {
        "name": "Finance Advisory Team",
        "service_line": ServiceLine.finance_advisory,
        "lead_name": "Samuel Okafor",
        "lead_email": "samuel.okafor@example.com",
        "is_default": False,
    },
    {
        "name": "Intake Desk",
        "service_line": None,
        "lead_name": "Jordan Pike",
        "lead_email": "jordan.pike@example.com",
        "is_default": True,
    },
]

# Hand-classified sample enquiries -- the classification fields
# (service_line, confidence, rationale, ...) are hand-written, not produced
# by a live model call, so the queue is populated with no API key needed.
# `team_service_line` is popped off and resolved to a real Team id in
# seed_if_needed() below rather than being a real Enquiry column.
ENQUIRIES = [
    dict(
        contact_name="Alicia Ferro",
        contact_email="alicia.ferro@meridianhealth.example.com",
        company_name="Meridian Health Systems",
        industry=Industry.healthcare,
        industry_other=None,
        company_size=CompanySize.size_251_1000,
        urgency=Urgency.within_month,
        description=(
            "We're migrating our patient records system to a new EHR platform and "
            "need help planning the data migration, validating outputs, and "
            "building reporting on top of it afterward."
        ),
        service_line=ServiceLine.data_analytics,
        complexity=Complexity.moderate,
        confidence=0.85,
        rationale=(
            "Core ask is a data migration and reporting build; healthcare is the "
            "client's industry, not the work needed."
        ),
        runner_up_service_line=ServiceLine.technology_transformation,
        runner_up_confidence=0.45,
        key_signals=["migrating our patient records system", "data migration", "building reporting"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.data_analytics,
        matched_rule="Data analytics catch-all",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Renata Kowalski",
        contact_email="renata.kowalski@ferrowmfg.example.com",
        company_name="Ferrow Manufacturing",
        industry=Industry.manufacturing,
        industry_other=None,
        company_size=CompanySize.size_1000_plus,
        urgency=Urgency.immediate,
        description=(
            "Our internal audit flagged gaps in supplier compliance documentation "
            "ahead of a regulatory review next month and we need an urgent risk "
            "assessment and remediation plan."
        ),
        service_line=ServiceLine.risk_compliance,
        complexity=Complexity.complex,
        confidence=0.88,
        rationale=(
            "Regulatory review with compliance documentation gaps is a risk & "
            "compliance engagement; urgency and scale point to complex."
        ),
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["internal audit flagged gaps", "supplier compliance documentation", "regulatory review"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.risk_compliance,
        matched_rule="Immediate complex risk & compliance",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Tomas Reyes",
        contact_email="tomas.reyes@brightretail.example.com",
        company_name="Bright Retail Co",
        industry=Industry.retail,
        industry_other=None,
        company_size=CompanySize.size_51_250,
        urgency=Urgency.exploring,
        description=(
            "We're a growing retailer curious about whether a phased approach to "
            "modernizing our point-of-sale and inventory systems makes sense, but "
            "haven't scoped anything yet."
        ),
        service_line=ServiceLine.technology_transformation,
        complexity=Complexity.moderate,
        confidence=0.79,
        rationale=(
            "POS and inventory system modernization is a technology "
            "transformation ask; exploring stage keeps scope open."
        ),
        runner_up_service_line=ServiceLine.operations,
        runner_up_confidence=0.5,
        key_signals=["modernizing our point-of-sale and inventory systems"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.technology_transformation,
        matched_rule="Complex technology transformation",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Helen Marsh",
        contact_email="helen.marsh@aldenpublicworks.example.gov",
        company_name="Alden Public Works",
        industry=Industry.public_sector,
        industry_other=None,
        company_size=CompanySize.size_1000_plus,
        urgency=Urgency.within_month,
        description=(
            "Our department needs to redesign several manual approval workflows "
            "that are creating bottlenecks in permit processing, and possibly "
            "renegotiate vendor contracts tied to those processes."
        ),
        service_line=ServiceLine.operations,
        complexity=Complexity.complex,
        confidence=0.7,
        rationale=(
            "Workflow redesign and bottleneck reduction is core operations work, "
            "but vendor renegotiation could pull in finance advisory too."
        ),
        runner_up_service_line=ServiceLine.finance_advisory,
        runner_up_confidence=0.58,
        key_signals=["redesign several manual approval workflows", "bottlenecks in permit processing"],
        flags=[Flag.multiple_service_lines],
        status=Status.routed,
        team_service_line=ServiceLine.operations,
        matched_rule="Operations catch-all",
        reviewed=True,
        was_corrected=False,
    ),
    dict(
        contact_name="Jae Kim",
        contact_email="jae.kim@novatech.example.com",
        company_name="NovaTech Systems",
        industry=Industry.technology,
        industry_other=None,
        company_size=CompanySize.size_1_50,
        urgency=Urgency.immediate,
        description="hi can you call me about this asap thanks",
        service_line=None,
        complexity=None,
        confidence=0.9,
        rationale=(
            "The description contains no information about the work needed, only "
            "a request to be contacted."
        ),
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["hi can you call me about this asap"],
        flags=[Flag.insufficient_information],
        status=Status.needs_review,
        team_service_line=None,
        matched_rule=None,
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="R. Dalton",
        contact_email="promo@quickcoinreturns.example.com",
        company_name="QuickCoin Returns",
        industry=Industry.other,
        industry_other="Cryptocurrency trading",
        company_size=CompanySize.size_1_50,
        urgency=Urgency.immediate,
        description=(
            "URGENT!!! Triple your investment in 30 days guaranteed, click here "
            "now to claim your bonus, act fast before this offer expires!!!"
        ),
        service_line=None,
        complexity=None,
        confidence=0.93,
        rationale=(
            "This reads as a promotional message rather than a genuine service "
            "enquiry; no legitimate scope is described."
        ),
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["Triple your investment", "guaranteed", "click here now"],
        flags=[Flag.spam, Flag.out_of_scope],
        status=Status.needs_review,
        team_service_line=None,
        matched_rule=None,
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Nora Falkirk",
        contact_email="nora.falkirk@falkirkwealth.example.com",
        company_name="Falkirk Wealth Partners",
        industry=Industry.financial_services,
        industry_other=None,
        company_size=CompanySize.size_51_250,
        urgency=Urgency.within_month,
        description=(
            "We want a valuation of our advisory business ahead of a potential "
            "minority stake sale and need someone to help us prepare the data "
            "room for buyer due diligence."
        ),
        service_line=ServiceLine.finance_advisory,
        complexity=Complexity.moderate,
        confidence=0.86,
        rationale="Valuation and due-diligence prep for a stake sale is squarely finance advisory work.",
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["valuation of our advisory business", "buyer due diligence", "data room"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.finance_advisory,
        matched_rule="Finance advisory catch-all",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Otto Brandt",
        contact_email="otto.brandt@solventchem.example.com",
        company_name="Solvent Chemicals Ltd",
        industry=Industry.manufacturing,
        industry_other=None,
        company_size=CompanySize.size_251_1000,
        urgency=Urgency.exploring,
        description=(
            "We're considering restructuring our workforce across two plants due "
            "to automation investments and want guidance on change management "
            "and communications planning."
        ),
        service_line=ServiceLine.people_change,
        complexity=Complexity.moderate,
        confidence=0.81,
        rationale="Workforce restructuring and change communications planning is a people & change engagement.",
        runner_up_service_line=ServiceLine.operations,
        runner_up_confidence=0.4,
        key_signals=["restructuring our workforce", "change management and communications planning"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.people_change,
        matched_rule="People & change catch-all",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Isabel Ochoa",
        contact_email="isabel.ochoa@ironcladinsurance.example.com",
        company_name="Ironclad Insurance Group",
        industry=Industry.financial_services,
        industry_other=None,
        company_size=CompanySize.size_1000_plus,
        urgency=Urgency.immediate,
        description=(
            "We suspect our claims processing system has compliance gaps that "
            "could expose us to regulatory penalties and need an urgent "
            "independent risk review before our next audit cycle."
        ),
        service_line=ServiceLine.risk_compliance,
        complexity=Complexity.complex,
        confidence=0.9,
        rationale=(
            "Compliance gap concerns ahead of an audit, with regulatory "
            "exposure, is a complex, urgent risk & compliance engagement."
        ),
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["compliance gaps", "regulatory penalties", "urgent independent risk review"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.risk_compliance,
        matched_rule="Immediate complex risk & compliance",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Sam Whitfield",
        contact_email="sam.whitfield@greenleafagritech.example.com",
        company_name="GreenLeaf Agritech",
        industry=Industry.other,
        industry_other="Agricultural technology",
        company_size=CompanySize.size_1_50,
        urgency=Urgency.within_month,
        description=(
            "We're a small agtech startup wanting to build out our first real "
            "reporting layer on top of our sensor data so we can actually see "
            "trends across our pilot farms."
        ),
        service_line=ServiceLine.data_analytics,
        complexity=Complexity.simple,
        confidence=0.84,
        rationale="A first reporting layer on existing sensor data for a small team is straightforward data analytics scope.",
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["reporting layer on top of our sensor data", "see trends across our pilot farms"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.data_analytics,
        matched_rule="Data analytics catch-all",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Diego Comstock",
        contact_email="diego.comstock@comstocklogistics.example.com",
        company_name="Comstock Logistics",
        industry=Industry.manufacturing,
        industry_other=None,
        company_size=CompanySize.size_251_1000,
        urgency=Urgency.immediate,
        description=(
            "We need an urgent operational review of our warehouse routing after "
            "two major shipment delays this month were traced back to system "
            "and process breakdowns."
        ),
        service_line=ServiceLine.operations,
        complexity=Complexity.moderate,
        confidence=0.77,
        rationale="Warehouse routing breakdowns tied to process and systems point to an operations review.",
        runner_up_service_line=ServiceLine.technology_transformation,
        runner_up_confidence=0.42,
        key_signals=["operational review of our warehouse routing", "shipment delays", "process breakdowns"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.operations,
        matched_rule="Operations catch-all",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Bea Hallwright",
        contact_email="bea.hallwright@redgatecounty.example.gov",
        company_name="Redgate County Council",
        industry=Industry.public_sector,
        industry_other=None,
        company_size=CompanySize.size_1000_plus,
        urgency=Urgency.within_month,
        description=(
            "We're replacing three legacy case-management systems across "
            "departments simultaneously and need a full technology "
            "transformation roadmap covering data migration, integration, and "
            "staff training."
        ),
        service_line=ServiceLine.technology_transformation,
        complexity=Complexity.complex,
        confidence=0.83,
        rationale=(
            "Replacing multiple legacy systems across departments with "
            "integration and training needs is a complex transformation program."
        ),
        runner_up_service_line=ServiceLine.people_change,
        runner_up_confidence=0.5,
        key_signals=["replacing three legacy case-management systems", "technology transformation roadmap", "staff training"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.technology_transformation,
        matched_rule="Complex technology transformation",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Priya Vantage",
        contact_email="priya.vantage@vantagebio.example.com",
        company_name="Vantage Bio Sciences",
        industry=Industry.healthcare,
        industry_other=None,
        company_size=CompanySize.size_51_250,
        urgency=Urgency.exploring,
        description=(
            "We might need help either building financial models for a funding "
            "round or restructuring our internal reporting - honestly still "
            "figuring out which matters more right now."
        ),
        service_line=ServiceLine.finance_advisory,
        complexity=Complexity.moderate,
        confidence=0.52,
        rationale=(
            "Financial modeling for a funding round leans finance advisory, but "
            "the internal reporting restructuring could also be data analytics; "
            "the client hasn't settled on scope."
        ),
        runner_up_service_line=ServiceLine.data_analytics,
        runner_up_confidence=0.45,
        key_signals=["financial models for a funding round", "restructuring our internal reporting"],
        flags=[Flag.multiple_service_lines],
        status=Status.needs_review,
        team_service_line=ServiceLine.finance_advisory,
        matched_rule="Finance advisory catch-all",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Wes Okonkwo",
        contact_email="wes.okonkwo@prairiestate.example.edu",
        company_name="Prairie State University",
        industry=Industry.public_sector,
        industry_other=None,
        company_size=CompanySize.size_1000_plus,
        urgency=Urgency.within_month,
        description=(
            "We need to plan a phased rollout of new HR and payroll systems for "
            "fourteen thousand staff, including union communications and "
            "training for department heads."
        ),
        service_line=ServiceLine.people_change,
        complexity=Complexity.complex,
        confidence=0.68,
        rationale=(
            "Large-scale rollout with union communications and training is "
            "people & change led, though the HR/payroll rollout also has a "
            "strong technology transformation component."
        ),
        runner_up_service_line=ServiceLine.technology_transformation,
        runner_up_confidence=0.6,
        key_signals=["phased rollout of new HR and payroll systems", "union communications", "training for department heads"],
        flags=[Flag.multiple_service_lines],
        status=Status.routed,
        team_service_line=ServiceLine.technology_transformation,
        matched_rule="Immediate people & change",
        reviewed=True,
        was_corrected=True,
    ),
    dict(
        contact_name="Claire Fenwick",
        contact_email="claire.fenwick@fenwickcole.example.com",
        company_name="Fenwick & Cole LLP",
        industry=Industry.professional_services,
        industry_other=None,
        company_size=CompanySize.size_1_50,
        urgency=Urgency.exploring,
        description=(
            "As a small partnership we want an outside view on whether our "
            "current billing and matter-management setup could be simplified, "
            "but we're not in a rush."
        ),
        service_line=ServiceLine.operations,
        complexity=Complexity.simple,
        confidence=0.8,
        rationale="A billing/matter-management simplification review for a small firm with no urgency is straightforward operations scope.",
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["billing and matter-management setup", "could be simplified"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.operations,
        matched_rule="Operations catch-all",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Harlan Doran",
        contact_email="harlan.doran@doranfreight.example.com",
        company_name="Doran Freight",
        industry=Industry.manufacturing,
        industry_other=None,
        company_size=CompanySize.size_51_250,
        urgency=Urgency.within_month,
        description=(
            "We are evaluating whether to consolidate two regional distribution "
            "centers and want an assessment of the operational and cost "
            "implications before deciding."
        ),
        service_line=None,
        complexity=None,
        confidence=None,
        rationale=None,
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=[],
        flags=[],
        status=Status.failed,
        team_service_line=None,
        matched_rule=None,
        error_message="Model output was truncated or did not match the schema.",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Miriam Hallcrest",
        contact_email="miriam.hallcrest@hallcrestunderwriters.example.com",
        company_name="Hallcrest Underwriters",
        industry=Industry.financial_services,
        industry_other=None,
        company_size=CompanySize.size_251_1000,
        urgency=Urgency.immediate,
        description=(
            "We just discovered our underwriting model hasn't been recalibrated "
            "against new regulatory capital requirements and need immediate "
            "risk and compliance support."
        ),
        service_line=ServiceLine.risk_compliance,
        complexity=Complexity.complex,
        confidence=0.91,
        rationale="Recalibrating against new regulatory capital requirements under time pressure is a complex, urgent compliance issue.",
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["underwriting model hasn't been recalibrated", "new regulatory capital requirements"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.risk_compliance,
        matched_rule="Immediate complex risk & compliance",
        reviewed=False,
        was_corrected=False,
    ),
    dict(
        contact_name="Yusuf Bramblewood",
        contact_email="yusuf.bramblewood@bramblewoodretail.example.com",
        company_name="Bramblewood Retail Group",
        industry=Industry.retail,
        industry_other=None,
        company_size=CompanySize.size_1000_plus,
        urgency=Urgency.within_month,
        description=(
            "We'd like a data warehouse and BI layer built across our forty "
            "stores so regional managers can finally see consistent sales and "
            "inventory reporting."
        ),
        service_line=ServiceLine.data_analytics,
        complexity=Complexity.moderate,
        confidence=0.87,
        rationale="A data warehouse and BI build across multiple stores is a clear data analytics engagement.",
        runner_up_service_line=None,
        runner_up_confidence=None,
        key_signals=["data warehouse and BI layer", "forty stores", "sales and inventory reporting"],
        flags=[],
        status=Status.routed,
        team_service_line=ServiceLine.data_analytics,
        matched_rule="Data analytics catch-all",
        reviewed=False,
        was_corrected=False,
    ),
]


def seed_if_needed() -> None:
    """Insert TEAMS and ENQUIRIES, but only into an empty database. Guards on
    `Team.count() > 0` so it's safe to call on every app startup (via
    SEED_ON_START) without duplicating rows on a restart."""
    session = SessionLocal()
    try:
        if session.query(Team).count() > 0:
            return

        teams = [Team(**t) for t in TEAMS]
        session.add_all(teams)
        session.commit()

        teams_by_service_line = {t.service_line: t for t in teams if t.service_line is not None}
        default_team = next(t for t in teams if t.is_default)

        for data in ENQUIRIES:
            data = dict(data)
            team_service_line = data.pop("team_service_line")
            team = teams_by_service_line.get(team_service_line, default_team if data["status"] != Status.failed else None)
            error_message = data.pop("error_message", None)
            flags = [f.value for f in data.pop("flags")]
            key_signals = data.pop("key_signals")

            enquiry = Enquiry(
                **data,
                team_id=team.id if team else None,
                routed_at=datetime.now(timezone.utc) if team else None,
                error_message=error_message,
                flags=flags,
                key_signals=key_signals,
            )
            session.add(enquiry)

        session.commit()
    finally:
        session.close()
