"""Frozen dataclass contracts for every stable yaml shape under data/.

The schedule.yaml output stays as a plain dict[str, Any] — only the inputs
(Substance/Product/Dashboard/Relation/TraitDef/Pillbox/Slot) become
dataclasses. The schedule warning union is also dict[str, Any] (its shape
is polymorphic and locally constructed inside cmd_plan).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

SlotNear = Literal[
    "wake", "breakfast", "day_meal", "sleep", "workout_before", "workout_after",
]
RelationType = Literal["balance", "supports", "competes", "antagonizes"]


class CardLoadError(Exception):
    """Raised when a YAML card fails to load or validate against its schema."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    traits: tuple[str, ...]
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    unmatched_concerns: tuple[str, ...] = ()
    prefer_with: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductComponent:
    substance: str
    label: str | None = None
    amount: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class Product:
    id: str
    name: str
    components: tuple[ProductComponent, ...]
    brand: str | None = None
    urls: tuple[str, ...] = ()
    notes: str | None = None
    unmatched_concerns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DashboardMember:
    substance: str | None = None
    name: str | None = None
    role: str | None = None
    note: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DashboardBenefit:
    description: str


@dataclass(frozen=True, slots=True)
class DashboardRisk:
    description: str
    warning_threshold: int
    action: str | None = None


@dataclass(frozen=True, slots=True)
class Dashboard:
    name: str
    description: str
    taking: tuple[DashboardMember, ...]
    benefit: DashboardBenefit | None = None
    risk: DashboardRisk | None = None
    started: str | None = None
    candidates: tuple[DashboardMember, ...] = ()
    declined: tuple[DashboardMember, ...] = ()


@dataclass(frozen=True, slots=True)
class Relation:
    type: RelationType
    reason: str
    source_substance: str | None = None
    target_substance: str | None = None
    source_name: str | None = None
    target_name: str | None = None
    action: str | None = None


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
class TraitDef:
    id: str
    namespace: str
    short_name: str
    label: str
    description: str
    applies_when: str
    effects: tuple[TraitEffect, ...] = ()
    separate_from: tuple[str, ...] = ()
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
