"""No DB connection and no ANTHROPIC_API_KEY required to run this file."""

import pytest

from app.models import Complexity, Industry, ServiceLine, Team, Urgency
from app.services import router


def _teams():
    """One team per service line plus a default catch-all, matching the
    shape seed.py produces -- used as fixture data across every test below."""
    return [
        Team(id=1, service_line=ServiceLine.data_analytics, is_default=False),
        Team(id=2, service_line=ServiceLine.risk_compliance, is_default=False),
        Team(id=3, service_line=ServiceLine.technology_transformation, is_default=False),
        Team(id=4, service_line=ServiceLine.finance_advisory, is_default=False),
        Team(id=5, service_line=ServiceLine.people_change, is_default=False),
        Team(id=6, service_line=ServiceLine.operations, is_default=False),
        Team(id=7, service_line=None, is_default=True),
    ]


def test_exact_match_specific_rule_wins_over_catch_all():
    """A context matching a specific, high-priority rule should route there
    rather than falling through to that service line's lower-priority
    catch-all rule."""
    context = {
        "service_line": ServiceLine.risk_compliance,
        "complexity": Complexity.complex,
        "urgency": Urgency.immediate,
        "industry": Industry.manufacturing,
    }
    team, rule_name = router.route(context, _teams())
    assert team.id == 2
    assert rule_name == "Immediate complex risk & compliance"


def test_priority_ordering_prefers_lower_priority_number():
    """When two rules both match, the one with the lower priority number
    should win -- here, "Healthcare risk & compliance" (priority 2) over the
    risk_compliance catch-all (priority 90)."""
    context = {
        "service_line": ServiceLine.risk_compliance,
        "complexity": Complexity.simple,
        "urgency": Urgency.exploring,
        "industry": Industry.healthcare,
    }
    team, rule_name = router.route(context, _teams())
    assert rule_name == "Healthcare risk & compliance"
    assert team.id == 2


def test_partial_conditions_ignore_unspecified_keys():
    """The "Exploring finance advisory" rule only constrains service_line
    and urgency; complexity/industry should not block the match even though
    they're present in the context and unconstrained by the rule."""
    context = {
        "service_line": ServiceLine.finance_advisory,
        "complexity": Complexity.complex,
        "urgency": Urgency.exploring,
        "industry": Industry.technology,
    }
    team, rule_name = router.route(context, _teams())
    assert rule_name == "Exploring finance advisory"
    assert team.id == 4


def test_no_match_falls_back_to_default_team():
    """A context no rule matches (no service_line at all, here) should
    route to the is_default team with no matched rule name."""
    context = {
        "service_line": None,
        "complexity": None,
        "urgency": Urgency.immediate,
        "industry": Industry.other,
    }
    team, rule_name = router.route(context, _teams())
    assert team.is_default is True
    assert rule_name is None


def test_no_default_team_raises_a_clear_error_instead_of_stopiteration():
    """If `teams` has no is_default row, route() must raise a clear
    ValueError rather than an unguarded `next()` StopIteration -- guards
    against a bug class already hit once elsewhere in this codebase."""
    teams_without_default = [Team(id=1, service_line=ServiceLine.operations, is_default=False)]
    context = {
        "service_line": None,
        "complexity": None,
        "urgency": Urgency.immediate,
        "industry": Industry.other,
    }
    with pytest.raises(ValueError, match="No default team"):
        router.route(context, teams_without_default)
