"""No DB connection and no ANTHROPIC_API_KEY required to run this file."""

from app.models import Flag, ServiceLine
from app.services.classifier import TriageResult, _normalize_enum


def test_triage_result_accepts_minimal_valid_payload():
    """The fields with defaults (key_signals, flags, runner_up_*) should be
    optional -- a payload giving only the required fields must still validate."""
    result = TriageResult(
        service_line="data_analytics",
        complexity="simple",
        confidence=0.9,
        rationale="Straightforward reporting build.",
    )
    assert result.key_signals == []
    assert result.flags == []
    assert result.runner_up_service_line is None


def test_triage_result_allows_null_service_line_and_complexity():
    """The insufficient-information case (nothing to classify) must validate
    with both fields explicitly null, not just omitted."""
    result = TriageResult(
        service_line=None, complexity=None, confidence=0.9, rationale="No scope given."
    )
    assert result.service_line is None
    assert result.complexity is None


def test_normalize_enum_handles_casing_and_separators():
    """Whitespace, mixed case, underscores, dashes, and multi-word values
    should all normalise onto the same enum member."""
    assert _normalize_enum(" Data_Analytics ", ServiceLine) == ServiceLine.data_analytics
    assert _normalize_enum("Risk-Compliance", ServiceLine) == ServiceLine.risk_compliance
    assert _normalize_enum("INSUFFICIENT INFORMATION", Flag) == Flag.insufficient_information


def test_normalize_enum_returns_none_for_unknown_value():
    """A string that normalises to no real enum member should return None,
    not raise -- an unrecognised value is dropped, not an error."""
    assert _normalize_enum("not_a_real_service_line", ServiceLine) is None


def test_normalize_enum_passes_through_none():
    """A None input (field genuinely absent) should stay None, not be
    coerced into a lookup attempt."""
    assert _normalize_enum(None, Flag) is None
