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
class GroomingCandidate:
    id: str
    name: str
    path: Path
    total_product_count: int
    active_product_count: int


@dataclass(frozen=True)
class GroomingResult:
    exit_code: int
    candidates: list[GroomingCandidate]
    limit: int
    total_remaining: int
    shown: int
    output: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class ResearchStateCandidate:
    kind: str
    id: str
    research_state: str
    detail: str
    sources: tuple[str, ...] = ()
    subject_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchStateCard:
    """Card-oriented grooming unit with assertion provenance retained."""

    id: str
    name: str
    path: Path
    total_product_count: int
    active_product_count: int
    active_product_names: tuple[str, ...]
    assertions: tuple[ResearchStateCandidate, ...]
    related_relations: tuple[ResearchStateCandidate, ...] = ()
    assessment_status: str = "wholly_unassessed"

    @property
    def unresolved_item_count(self) -> int:
        """Facts plus distinct relation leads shown for this card."""
        return len(self.assertions) + len({relation.id for relation in self.related_relations})


@dataclass(frozen=True)
class ResearchStateResult:
    exit_code: int
    cards: list[ResearchStateCard]
    research_state: str
    limit: int
    total_matching: int
    shown: int
    assertion_count: int = 0
    output: str = ""
    stderr: str = ""

    @property
    def candidates(self) -> list[ResearchStateCandidate]:
        """Flattened provenance view retained for callers of the old API."""
        return [assertion for card in self.cards for assertion in (*card.assertions, *card.related_relations)]


@dataclass(frozen=True)
class ShowResult:
    exit_code: int
    output: str = ""


@dataclass(frozen=True)
class AuditResult:
    exit_code: int
    cleanup: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    full: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
