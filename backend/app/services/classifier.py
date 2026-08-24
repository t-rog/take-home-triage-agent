"""The only module that imports `anthropic`. Everything else is testable offline."""

import time
from dataclasses import dataclass

from anthropic import Anthropic
from pydantic import BaseModel, Field

from ..config import settings
from ..domain import COMPLEXITY_RUBRIC, SERVICE_LINE_DESCRIPTIONS
from ..models import Complexity, Flag, ServiceLine
from ..schemas import EnquiryCreate

PROMPT_VERSION = "v1"

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """Lazily construct and cache the Anthropic client at first use rather
    than at import time, so importing this module never requires a key to
    already be set (useful for tests that never actually call the API)."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60.0)
    return _client


class TriageResult(BaseModel):
    """Schema handed to the model. Fields that map to enums are plain strings —
    the API's enum casing is not guaranteed to match ours exactly, so we
    normalise after parsing rather than trusting Pydantic's own enum
    validation to succeed on the first try."""

    service_line: str | None = Field(
        description="One of the service line keys, or null if the description "
        "gives nothing to classify."
    )
    complexity: str | None = Field(
        description="One of the complexity keys, or null alongside a null "
        "service_line."
    )
    confidence: float = Field(
        description="How often a senior analyst at the firm would agree with "
        "this classification, from 0 to 1."
    )
    rationale: str = Field(description="2-3 sentences a reviewing analyst can act on.")
    runner_up_service_line: str | None = Field(
        default=None, description="Second most plausible service line, if any."
    )
    runner_up_confidence: float | None = Field(default=None)
    key_signals: list[str] = Field(
        default_factory=list, description="Verbatim phrases from the description."
    )
    flags: list[str] = Field(default_factory=list)


@dataclass
class ClassificationResult:
    """The normalised, enum-typed result of one successful classify() call --
    TriageResult's raw strings converted to real ServiceLine/Complexity/Flag
    members, plus the token/timing telemetry the caller needs to persist."""

    service_line: ServiceLine | None
    complexity: Complexity | None
    confidence: float
    rationale: str
    runner_up_service_line: ServiceLine | None
    runner_up_confidence: float | None
    key_signals: list[str]
    flags: list[Flag]
    input_tokens: int
    output_tokens: int
    latency_ms: int


class ClassificationError(Exception):
    """Raised when classify() cannot produce a usable result after its one
    retry. `outcome` is a short machine-readable tag (e.g. "refusal",
    "schema_error", "api_error") and `message` is written straight into
    Enquiry.error_message for the Failed tab to display."""

    def __init__(self, outcome: str, message: str):
        self.outcome = outcome
        self.message = message
        super().__init__(message)


def _normalize_enum(value: str | None, enum_cls):
    """Map a model-returned string onto a real enum member, tolerating the
    casing/spacing drift the Claude docs warn structured outputs can still
    have (e.g. "Data Analytics" or "data-analytics" for `data_analytics`).
    Returns None for null input or for a value that still doesn't match any
    member after normalising -- callers treat that the same as "the model
    didn't give us this field," not as an error."""
    if value is None:
        return None
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    try:
        return enum_cls(key)
    except ValueError:
        return None


def _build_system_prompt() -> str:
    """Assemble the system prompt from domain.py's service-line descriptions
    and complexity rubric (not a string constant) so both stay in sync with
    the one shared source of truth, plus worked examples covering a clear
    case, an ambiguous multi-service-line case, and an insufficient-info case."""
    lines_desc = "\n".join(
        f"- {sl.value}: {desc}" for sl, desc in SERVICE_LINE_DESCRIPTIONS.items()
    )
    return f"""You triage inbound enquiries for a professional services firm.

Service lines:
{lines_desc}

Complexity rubric:
{COMPLEXITY_RUBRIC}

Rules:
- Choose the service line describing the work needed, not the client's
  industry. A healthcare company asking for a data migration is
  data_analytics, not a health-specific line.
- Judge complexity on scope, number of systems or stakeholders, ambiguity,
  and whether discovery is needed. Urgency and company size alone do not
  determine complexity.
- Express confidence as how often a senior analyst would agree with this
  exact classification, not as your abstract certainty.
- Set runner_up_service_line and runner_up_confidence whenever a second
  service line is plausible, even if the first choice feels clear. The
  margin between the two matters more than the absolute score.
- If the description gives nothing to classify (e.g. "hi can you call me"),
  return null for service_line and complexity and set the
  insufficient_information flag rather than guessing.
- Put verbatim phrases from the description in key_signals.
- Keep rationale to 2-3 sentences addressed to an analyst deciding whether
  to agree with you.

Examples:

1. Description: "We're a 300-person healthcare provider migrating our
   patient records system to a new EHR platform and need help planning the
   data migration and validating outputs afterward."
   -> service_line=data_analytics, complexity=moderate, confidence=0.82,
      runner_up_service_line=technology_transformation,
      runner_up_confidence=0.55,
      key_signals=["migrating our patient records system", "data migration",
      "validating outputs"], flags=[]

2. Description: "Not sure exactly what we need yet, but we're growing fast
   and things feel disorganized across finance and ops. Might need
   restructuring, might need new systems, might just need a review."
   -> service_line=operations, complexity=complex, confidence=0.48,
      runner_up_service_line=finance_advisory, runner_up_confidence=0.4,
      key_signals=["disorganized across finance and ops", "might need
      restructuring"], flags=["multiple_service_lines"]

3. Description: "hi can you call me"
   -> service_line=null, complexity=null, confidence=0.9,
      key_signals=["hi can you call me"], flags=["insufficient_information"]

Respond only with the structured fields."""


def _build_user_message(enquiry: EnquiryCreate) -> str:
    """Format one enquiry's submitted fields as the user turn. Substitutes
    the free-text `industry_other` in place of the literal "other" enum
    value so the model sees the client's actual stated industry."""
    industry = (
        enquiry.industry_other if enquiry.industry.value == "other" else enquiry.industry.value
    )
    return (
        f"Industry: {industry}\n"
        f"Company size: {enquiry.company_size.value}\n"
        f"Urgency: {enquiry.urgency.value}\n"
        f"Description: {enquiry.description}"
    )


def classify(enquiry: EnquiryCreate) -> ClassificationResult:
    """Public entry point: classify one enquiry via Claude. Thin wrapper
    around _classify() that just seeds the retry flag -- kept separate so
    callers never have to think about the `retried` parameter."""
    return _classify(enquiry, retried=False)


def _classify(enquiry: EnquiryCreate, retried: bool) -> ClassificationResult:
    """Make one classification call, retrying at most once via a recursive
    self-call with `retried=True`. Two failure modes get that one retry:
    any raised exception (including a missing/invalid API key, which
    surfaces as a bare TypeError before any request is even sent) and a
    truncated/schema-mismatched response. A refusal is treated as terminal
    immediately -- retrying the same input would just refuse again. Once
    `retried` is already True, any further failure raises
    ClassificationError instead of trying a third time."""
    start = time.monotonic()
    try:
        response = _get_client().messages.parse(
            model=settings.MODEL_ID,
            max_tokens=1024 if not retried else 2048,
            system=_build_system_prompt(),
            messages=[{"role": "user", "content": _build_user_message(enquiry)}],
            output_format=TriageResult,
        )
    except Exception as e:
        # Broad on purpose: auth misconfiguration raises a bare TypeError from
        # the SDK before any request is sent, not an APIError, and a failed
        # enquiry must still surface a clean error rather than a 500.
        if retried:
            raise ClassificationError("api_error", str(e)) from e
        return _classify(enquiry, retried=True)

    latency_ms = int((time.monotonic() - start) * 1000)

    if response.stop_reason == "refusal":
        raise ClassificationError("refusal", "Model refused to classify this enquiry.")

    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        if retried:
            raise ClassificationError(
                "schema_error", "Model output was truncated or did not match the schema."
            )
        return _classify(enquiry, retried=True)

    parsed = response.parsed_output
    flags = [f for f in (_normalize_enum(x, Flag) for x in parsed.flags) if f is not None]

    return ClassificationResult(
        service_line=_normalize_enum(parsed.service_line, ServiceLine),
        complexity=_normalize_enum(parsed.complexity, Complexity),
        confidence=parsed.confidence,
        rationale=parsed.rationale,
        runner_up_service_line=_normalize_enum(parsed.runner_up_service_line, ServiceLine),
        runner_up_confidence=parsed.runner_up_confidence,
        key_signals=parsed.key_signals,
        flags=flags,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )


if __name__ == "__main__":
    import sys

    from ..models import CompanySize, Industry, Urgency

    description = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "We need help migrating our legacy CRM data into a new platform "
        "and building automated reporting on top of it."
    )
    sample = EnquiryCreate(
        contact_name="Test Contact",
        contact_email="test@example.com",
        company_name="Test Co",
        industry=Industry.technology,
        company_size=CompanySize.size_51_250,
        urgency=Urgency.within_month,
        description=description,
    )
    print(classify(sample))
