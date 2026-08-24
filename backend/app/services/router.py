"""Pure function: classification + enquiry context -> team. No DB, no API calls.

Rules are a plain Python list rather than a database table: nothing in this
app edits them at runtime, so a table would only add a migration and a seed
step for no behavioural benefit. To change routing policy, edit RULES.
"""

from ..models import Complexity, Industry, ServiceLine, Team, Urgency

RULES: list[dict] = [
    {
        "name": "Immediate complex risk & compliance",
        "priority": 1,
        "conditions": {
            "service_line": ServiceLine.risk_compliance,
            "complexity": [Complexity.complex],
            "urgency": [Urgency.immediate],
        },
        "team_service_line": ServiceLine.risk_compliance,
    },
    {
        "name": "Healthcare risk & compliance",
        "priority": 2,
        "conditions": {
            "service_line": ServiceLine.risk_compliance,
            "industry": [Industry.healthcare],
        },
        "team_service_line": ServiceLine.risk_compliance,
    },
    {
        "name": "Complex technology transformation",
        "priority": 3,
        "conditions": {
            "service_line": ServiceLine.technology_transformation,
            "complexity": [Complexity.complex, Complexity.moderate],
        },
        "team_service_line": ServiceLine.technology_transformation,
    },
    {
        "name": "Exploring finance advisory",
        "priority": 4,
        "conditions": {
            "service_line": ServiceLine.finance_advisory,
            "urgency": [Urgency.exploring],
        },
        "team_service_line": ServiceLine.finance_advisory,
    },
    {
        "name": "Immediate people & change",
        "priority": 5,
        "conditions": {
            "service_line": ServiceLine.people_change,
            "urgency": [Urgency.immediate, Urgency.within_month],
        },
        "team_service_line": ServiceLine.people_change,
    },
    {
        "name": "Risk & compliance catch-all",
        "priority": 90,
        "conditions": {"service_line": ServiceLine.risk_compliance},
        "team_service_line": ServiceLine.risk_compliance,
    },
    {
        "name": "Data analytics catch-all",
        "priority": 91,
        "conditions": {"service_line": ServiceLine.data_analytics},
        "team_service_line": ServiceLine.data_analytics,
    },
    {
        "name": "Operations catch-all",
        "priority": 92,
        "conditions": {"service_line": ServiceLine.operations},
        "team_service_line": ServiceLine.operations,
    },
    {
        "name": "Technology transformation catch-all",
        "priority": 93,
        "conditions": {"service_line": ServiceLine.technology_transformation},
        "team_service_line": ServiceLine.technology_transformation,
    },
    {
        "name": "People & change catch-all",
        "priority": 94,
        "conditions": {"service_line": ServiceLine.people_change},
        "team_service_line": ServiceLine.people_change,
    },
    {
        "name": "Finance advisory catch-all",
        "priority": 95,
        "conditions": {"service_line": ServiceLine.finance_advisory},
        "team_service_line": ServiceLine.finance_advisory,
    },
]


def _value_of(v):
    """Unwrap an enum member to its `.value`, or pass through unchanged --
    lets _matches() compare enum members and plain values interchangeably
    without the caller having to normalise first."""
    return v.value if hasattr(v, "value") else v


def _matches(conditions: dict, context: dict) -> bool:
    """True if every key in `conditions` matches the corresponding value in
    `context`. A condition value can be a single value (exact match) or a
    list (context value must be one of them). Keys absent from `conditions`
    are unconstrained -- this is what makes a rule "partial" (e.g. matching
    on service_line + urgency while ignoring complexity/industry)."""
    for key, expected in conditions.items():
        actual = _value_of(context.get(key))
        if isinstance(expected, list):
            if actual not in [_value_of(e) for e in expected]:
                return False
        elif actual != _value_of(expected):
            return False
    return True


def route(context: dict, teams: list[Team]) -> tuple[Team, str | None]:
    """Pick a team for one enquiry. `context` keys are service_line,
    complexity, urgency, industry (enum members or None). Evaluates RULES in
    ascending priority order and returns the first match's team plus the
    rule's name (for display/audit); falls back to the one `is_default`
    team with rule_name=None if nothing matches. Raises ValueError if no
    default team exists in `teams` -- that's a seed-data bug, not a
    per-enquiry failure, so it isn't swallowed."""
    for rule in sorted(RULES, key=lambda r: r["priority"]):
        if _matches(rule["conditions"], context):
            team = next(
                (t for t in teams if t.service_line == rule["team_service_line"]), None
            )
            if team is not None:
                return team, rule["name"]

    default_team = next((t for t in teams if t.is_default), None)
    if default_team is None:
        raise ValueError("No default team configured -- routing cannot fall back.")
    return default_team, None
