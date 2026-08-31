"""Engine subpackage: re-exports cmd_* and result dataclasses for the CLI entrypoint."""

from pathlib import Path

from planner.engine.check import cmd_check
from planner.engine.find import cmd_find
from planner.engine.plan import cmd_plan
from planner.engine.results import (
    CheckResult,
    FindResult,
    PlanResult,
    ReviewResult,
    ShowResult,
)
from planner.engine.show import cmd_show


def cmd_review(data_root: Path | None = None) -> ReviewResult:
    """Load legacy review dependencies only when the review command is used."""
    from planner.engine.review import cmd_review as _cmd_review

    return _cmd_review(data_root)


__all__ = [
    "CheckResult",
    "FindResult",
    "PlanResult",
    "ReviewResult",
    "ShowResult",
    "cmd_check",
    "cmd_find",
    "cmd_plan",
    "cmd_review",
    "cmd_show",
]
