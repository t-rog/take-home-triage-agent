"""Business-domain reference text, shared by the classifier prompt
(services/classifier.py) and the `/api/service-lines` endpoint
(api/reference.py) so both read from one definition instead of drifting."""

from .models import ServiceLine

SERVICE_LINE_DESCRIPTIONS: dict[ServiceLine, str] = {
    ServiceLine.data_analytics: (
        "Data platforms, migrations, reporting, dashboards, and analytics builds."
    ),
    ServiceLine.risk_compliance: (
        "Regulatory compliance, audit readiness, risk frameworks, and controls testing."
    ),
    ServiceLine.operations: (
        "Process redesign, supply chain, cost reduction, and operational efficiency work."
    ),
    ServiceLine.technology_transformation: (
        "System implementations, platform migrations, IT strategy, and technology roadmaps."
    ),
    ServiceLine.people_change: (
        "Organisational design, change management, workforce planning, and training rollouts."
    ),
    ServiceLine.finance_advisory: (
        "Financial planning, M&A due diligence, valuations, and finance function advisory."
    ),
}

# Injected verbatim into the classifier's system prompt so the model judges
# complexity on scope/ambiguity rather than on urgency or company size.
COMPLEXITY_RUBRIC = (
    "simple: a single system or stakeholder, well-defined scope, no discovery needed. "
    "moderate: a few systems or stakeholders, some ambiguity, limited discovery required. "
    "complex: many systems or stakeholders, significant ambiguity, or a discovery phase "
    "is clearly needed before scoping can even begin."
)
