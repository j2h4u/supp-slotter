"""Result dataclasses for cmd_* functions.

Each dataclass carries at minimum ``exit_code: int`` plus the structured data
the corresponding command produces, so callers can assert on fields rather than
parsing stdout strings.

Humanized warning text lives in the stdout/yaml path of cmd_plan only;
``PlanResult.warnings`` is the raw pre-humanize dict list.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    exit_code: int
    errors: list[str]
    info: list[str]


@dataclass(frozen=True)
class PlanResult:
    exit_code: int
    schedule_written: bool
    warnings: list[dict[str, Any]]
    slot_loads: dict[str, int]
    prefer_pairs_declared: int
    prefer_pairs_together: int


@dataclass(frozen=True)
class DoctorResult:
    exit_code: int
    sections: dict[str, list[str]]


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
    by_kind: dict[str, list[tuple[str, str]]]
