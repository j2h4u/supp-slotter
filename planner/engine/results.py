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

from planner.engine._types import ScheduleWarning


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
    prefer_pairs_declared: int
    prefer_pairs_together: int
    errors: list[str] = field(default_factory=list[str])


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


@dataclass(frozen=True)
class ShowResult:
    exit_code: int
    output: str = ""


@dataclass(frozen=True)
class AuditResult:
    exit_code: int
    cleanup: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    full: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
