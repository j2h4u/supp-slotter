"""Engine subpackage: re-exports cmd_* and result dataclasses for the CLI entrypoint."""

from planner.engine.check import cmd_check
from planner.engine.find import cmd_find
from planner.engine.grooming import cmd_groom
from planner.engine.plan import cmd_plan
from planner.engine.results import (
    CheckResult,
    FindResult,
    GroomAssessment,
    GroomKnowledge,
    GroomProduct,
    GroomRelation,
    GroomResult,
    GroomSchedule,
    GroomWorkItem,
    PlanResult,
    ReviewResult,
    ShowResult,
)
from planner.engine.show import cmd_show


def cmd_review(data_root=None):  # type: ignore[no-untyped-def]
    """Load legacy review dependencies only when the review command is used."""
    from planner.engine.review import cmd_review as _cmd_review

    return _cmd_review(data_root)


__all__ = [
    "CheckResult",
    "FindResult",
    "GroomAssessment",
    "GroomKnowledge",
    "GroomProduct",
    "GroomRelation",
    "GroomResult",
    "GroomSchedule",
    "GroomWorkItem",
    "PlanResult",
    "ReviewResult",
    "ShowResult",
    "cmd_check",
    "cmd_find",
    "cmd_groom",
    "cmd_plan",
    "cmd_review",
    "cmd_show",
]
