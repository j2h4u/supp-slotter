"""Frozen dataclass contracts for every stable yaml shape under data/.

The schedule.yaml output stays as typed dictionary records — only the inputs
(Substance/Product/Dashboard/Relation/SchedulingPolicy/Pillbox/Slot) become
dataclasses. Schedule warnings are polymorphic typed dictionaries constructed
inside the planner engine.

Dashboard selector resolution is union (logical OR): a substance belongs when it
carries at least one declared category/term selector.

Substance carries scheduling fields (intake, timing, activity, prefer_with) and
canonical knowledge fields (kind, role, quality, effect, risk, context, pathway).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple, TypedDict

SlotNear = Literal[
    "wake",
    "breakfast",
    "day_meal",
    "sleep",
    "workout_before",
    "workout_after",
]
RelationType = Literal["balance", "supports", "competes", "review_with"]
Severity = Literal["critical", "high", "medium", "low"]
ConcernKind = Literal["safety", "model_gap", "data_quality"]


@dataclass(frozen=True, slots=True)
class Concern:
    kind: ConcernKind
    text: str


class CardLoadError(Exception):
    """Raised when a YAML card fails to load or validate against its schema."""

    path: Path
    message: str

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    # --- schedule: section (Planner reads these) ---
    intake: tuple[str, ...] = ()  # 0 or 1 slug
    timing: tuple[str, ...] = ()  # 0 or 1 slug — NEW
    activity: tuple[str, ...] = ()  # 0 or 1 slug
    prefer_with: tuple[str, ...] = ()  # sub_* IDs
    # --- knowledge: section (Reviewer reads these) ---
    kind: tuple[str, ...] = ()
    role: tuple[str, ...] = ()
    quality: tuple[str, ...] = ()
    effect: tuple[str, ...] = ()  # non-scheduling pharmacology only
    risk: tuple[str, ...] = ()
    context: tuple[str, ...] = ()
    pathway: tuple[str, ...] = ()  # NEW
    # --- common ---
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductComponent:
    substance: str
    label: str | None = None
    amount: str | None = None
    notes: str | None = None
    # None = unset; inference in effective_stack_item_traits:
    # if any sibling has primary=True, unset components are secondary.
    primary: bool | None = None


@dataclass(frozen=True, slots=True)
class Product:
    id: str
    name: str
    components: tuple[ProductComponent, ...]
    brand: str | None = None
    urls: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()


class StackEntry(TypedDict):
    product: str
    stack: str


@dataclass(frozen=True, slots=True)
class DashboardBenefit:
    description: str


@dataclass(frozen=True, slots=True)
class DashboardRisk:
    description: str


@dataclass(frozen=True, slots=True)
class Dashboard:
    name: str
    description: str
    selectors: tuple[RelationSelector, ...]
    benefit: DashboardBenefit | None = None
    risk: DashboardRisk | None = None
    started: str | None = None


@dataclass(frozen=True, slots=True)
class RelationSelector:
    """A canonical relation endpoint: exactly one entity or category/term pair."""

    entity_id: str | None = None
    entity_name: str | None = None
    category: str | None = None
    term: str | None = None


@dataclass(frozen=True, slots=True)
class Relation:
    id: str
    type: RelationType
    reason: str
    source_selector: RelationSelector
    target_selector: RelationSelector
    action: str | None = None
    severity: Severity | None = None


@dataclass(frozen=True, slots=True)
class TraitEffectMatch:
    near: SlotNear | None = None
    food: bool | None = None


@dataclass(frozen=True, slots=True)
class TraitEffect:
    match: TraitEffectMatch
    level: Literal["avoid_strong", "avoid", "prefer", "prefer_strong"] | None = None
    block: bool | None = None


@dataclass(frozen=True, slots=True)
class SchedulingPolicy:
    id: str
    namespace: str
    short_name: str
    label: str
    description: str
    applies_when: str
    effects: tuple[TraitEffect, ...] = ()
    warning: bool = False
    action: str | None = None


@dataclass(frozen=True, slots=True)
class Slot:
    """One pillbox slot, post-flatten.

    The pillbox, pillbox_label, and stack fields are NOT part of the on-disk slot schema;
    they are joined in by load_pillboxes when it assembles Slot instances from the raw
    pillbox YAML data.
    """

    slot_id: str
    label: str
    order: int
    near: SlotNear
    food: bool
    pillbox: str
    pillbox_label: str
    stack: str


@dataclass(frozen=True, slots=True)
class Pillbox:
    name: str
    label: str
    # key = slot_id; values are flattened Slot instances joined with pillbox/stack metadata at load time.
    slots: dict[str, Slot]


class FindResult(NamedTuple):
    score: float
    card_id: str
    label: str
    path: Path
