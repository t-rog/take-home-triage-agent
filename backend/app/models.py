"""SQLAlchemy models and the enums that back them.

Two tables only: `Team` (a lookup of who can receive enquiries) and
`Enquiry` (one row per submission, holding the client's original request,
the model's classification, and the routing outcome, all in place -- no
history tables). See PROJECT_PLAN.md §8 for the reasoning.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base; both models below inherit from this."""


def _utcnow() -> datetime:
    """Timezone-aware "now", used as the default for every timestamp column."""
    return datetime.now(timezone.utc)


class Industry(str, Enum):
    """The client's industry, as selected on the intake form."""

    financial_services = "financial_services"
    healthcare = "healthcare"
    manufacturing = "manufacturing"
    retail = "retail"
    public_sector = "public_sector"
    technology = "technology"
    professional_services = "professional_services"
    other = "other"


class CompanySize(str, Enum):
    """The client's headcount bracket, as selected on the intake form."""

    size_1_50 = "size_1_50"
    size_51_250 = "size_51_250"
    size_251_1000 = "size_251_1000"
    size_1000_plus = "size_1000_plus"


class Urgency(str, Enum):
    """How soon the client says they need this addressed. Feeds both the
    classifier's complexity judgment and the router's rule conditions."""

    exploring = "exploring"
    within_month = "within_month"
    immediate = "immediate"


class ServiceLine(str, Enum):
    """What kind of work the enquiry needs. Set by the classifier (describing
    the work, not the client's industry), and the field routing rules match
    on to pick a team."""

    data_analytics = "data_analytics"
    risk_compliance = "risk_compliance"
    operations = "operations"
    technology_transformation = "technology_transformation"
    people_change = "people_change"
    finance_advisory = "finance_advisory"


class Complexity(str, Enum):
    """The classifier's estimate of scope/ambiguity, per domain.COMPLEXITY_RUBRIC."""

    simple = "simple"
    moderate = "moderate"
    complex = "complex"


class Status(str, Enum):
    """Where an enquiry currently stands. `routed` and `needs_review` both
    have a team assigned (the latter just needs a human to confirm it);
    `failed` means classification itself never produced a result; `closed`
    means a reviewer dismissed it (spam/out of scope) without routing it."""

    routed = "routed"
    needs_review = "needs_review"
    failed = "failed"
    closed = "closed"


class Flag(str, Enum):
    """Signals the classifier can attach alongside a classification. Any
    non-empty flag list sends the enquiry to `needs_review` regardless of
    confidence -- see pipeline._needs_review."""

    insufficient_information = "insufficient_information"
    out_of_scope = "out_of_scope"
    spam = "spam"
    multiple_service_lines = "multiple_service_lines"


def _enum_column(enum_cls, name, **kwargs):
    """Build a mapped_column backed by a Postgres enum type, storing the
    lowercase `.value` of each member rather than the member's Python name.
    `name` is the Postgres enum type name -- pass the same name for every
    column that should share one underlying type (e.g. all `ServiceLine`
    columns use "service_line_enum") so it's created once, not once per
    column."""
    return mapped_column(
        SAEnum(enum_cls, values_callable=lambda e: [m.value for m in e], name=name),
        **kwargs,
    )


class Team(Base):
    """A group that can receive enquiries, led by one named person
    (`lead_name`/`lead_email` -- there's no separate roster of individual
    staff). `service_line=None` marks the catch-all "Intake Desk" team;
    exactly one row should have `is_default=True`, which is where
    `router.route()` falls back to when no rule matches. Seeded in
    `seed.py`, never created through the API."""

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    service_line: Mapped[ServiceLine | None] = _enum_column(
        ServiceLine, "service_line_enum", nullable=True
    )
    lead_name: Mapped[str] = mapped_column(String(120))
    lead_email: Mapped[str] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Enquiry(Base):
    """One inbound enquiry, from submission through classification and
    routing to (optionally) human review -- all on a single row that gets
    updated in place rather than versioned. The client-submitted fields
    (contact info, industry, description, ...) never change after creation;
    everything from `service_line` onward is written by the classify/route
    pipeline (`services/pipeline.py`) and can be overwritten later by a
    human correction via the `/review` endpoint."""

    __tablename__ = "enquiry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contact_name: Mapped[str] = mapped_column(String(120))
    contact_email: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[Industry] = _enum_column(Industry, "industry_enum")
    industry_other: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_size: Mapped[CompanySize] = _enum_column(CompanySize, "company_size_enum")
    urgency: Mapped[Urgency] = _enum_column(Urgency, "urgency_enum")
    description: Mapped[str] = mapped_column(Text)

    service_line: Mapped[ServiceLine | None] = _enum_column(
        ServiceLine, "service_line_enum", nullable=True
    )
    complexity: Mapped[Complexity | None] = _enum_column(
        Complexity, "complexity_enum", nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    runner_up_service_line: Mapped[ServiceLine | None] = _enum_column(
        ServiceLine, "service_line_enum", nullable=True
    )
    runner_up_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    key_signals: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[Status] = _enum_column(Status, "status_enum")
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"), nullable=True)
    matched_rule: Mapped[str | None] = mapped_column(String(200), nullable=True)
    routed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    was_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    team: Mapped["Team | None"] = relationship("Team")
