"""Result dataclasses for cmd_* functions.

Each dataclass carries at minimum ``exit_code: int`` plus the structured data
the corresponding command produces, so callers can assert on fields rather than
parsing stdout strings.

Humanized warning text lives in the stdout/yaml path of cmd_plan only;
``PlanResult.warnings`` is the raw pre-humanize dict list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from planner.canonical_optimizer_result import Diagnostic
from planner.schedule_types import ScheduleWarning


@dataclass(frozen=True)
class CheckResult:
    exit_code: int
    errors: list[str]
    info: list[str]


@dataclass(frozen=True)
class PlanResult:
    exit_code: int
    schedule_written: bool
    warnings: list[ScheduleWarning]
    slot_loads: dict[str, int]
    errors: list[str] = field(default_factory=list[str])
    diagnostic: Diagnostic | None = None

    @property
    def status(self) -> str:
        """Publication status exposed by the canonical plan boundary."""
        return "Optimal" if self.schedule_written else "Indeterminate"


@dataclass(frozen=True)
class FindResult:
    exit_code: int
    query: str
    substances: list[tuple[float, str, str, Path]]
    products: list[tuple[float, str, str, Path]]


@dataclass(frozen=True)
class ReviewResult:
    exit_code: int
    output: str = ""
    stderr: str = ""


@dataclass(frozen=True, slots=True)
class GroomWorkItem:
    """One selected component role whose operational receipt is absent."""

    composition_role_id: str
    product_id: str
    product_name: str
    substance_id: str
    substance_name: str

    @property
    def id(self) -> str:
        return self.composition_role_id


@dataclass(frozen=True, slots=True)
class GroomResult:
    exit_code: int
    work_item: GroomWorkItem | None
    eligible_count: int
    output: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class ShowResult:
    exit_code: int
    output: str = ""
