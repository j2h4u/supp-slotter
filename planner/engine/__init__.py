"""Engine subpackage: re-exports cmd_* and result dataclasses for the CLI entrypoint."""

from planner.engine.audit import cmd_audit
from planner.engine.check import cmd_check
from planner.engine.doctor import cmd_doctor
from planner.engine.find import cmd_find
from planner.engine.plan import cmd_plan
from planner.engine.results import (
    AuditResult,
    CheckResult,
    DoctorResult,
    FindResult,
    PlanResult,
    ReviewResult,
    ShowResult,
)
from planner.engine.review import cmd_review_substance
from planner.engine.show import cmd_show

__all__ = [
    "cmd_audit",
    "cmd_check",
    "cmd_doctor",
    "cmd_find",
    "cmd_plan",
    "cmd_review_substance",
    "cmd_show",
    "AuditResult",
    "CheckResult",
    "DoctorResult",
    "FindResult",
    "PlanResult",
    "ReviewResult",
    "ShowResult",
]
