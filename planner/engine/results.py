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


@dataclass(frozen=True, slots=True)
class GroomProduct:
    id: str
    name: str
    brand: str | None
    notes: str | None
    use_pattern: str | None
    components: tuple[tuple[str, str | None, str | None, str | None], ...]


@dataclass(frozen=True, slots=True)
class GroomKnowledge:
    category: str
    value: str
    research_state: str
    sources: tuple[str, ...]

    @property
    def open(self) -> bool:
        return self.research_state == "unassessed"


@dataclass(frozen=True, slots=True)
class GroomRelation:
    id: str
    relation_type: str
    source: str
    target: str
    reason: str
    research_state: str
    sources: tuple[str, ...]
    active_endpoint_ids: tuple[str, ...]
    owner_id: str

    @property
    def open(self) -> bool:
        return self.research_state == "unassessed"


@dataclass(frozen=True, slots=True)
class GroomSchedule:
    axis: str
    value: str


@dataclass(frozen=True, slots=True)
class GroomAssessment:
    axis: str
    conclusion: str
    policy: str | None
    sources: tuple[str, ...]
    summary: str

    @property
    def open(self) -> bool:
        return self.conclusion == "unassessed"


@dataclass(frozen=True, slots=True)
class GroomWorkItem:
    """One immutable, complete substance-card grooming dossier."""

    substance_id: str
    name: str
    path: Path
    aliases: tuple[str, ...]
    form: str | None
    notes: str | None
    active_unique_product_count: int
    open_owned_item_count: int
    active_products: tuple[GroomProduct, ...]
    knowledge: tuple[GroomKnowledge, ...]
    open_relations: tuple[GroomRelation, ...]
    schedule_assertions: tuple[GroomSchedule, ...]
    scheduling_assessments: tuple[GroomAssessment, ...]

    @property
    def id(self) -> str:
        return self.substance_id


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
