"""Frozen dataclass contracts for every stable yaml shape under data/.

The schedule.yaml output stays as typed dictionary records — only the inputs
(Substance/Product/Dashboard/Relation/Pillbox/Slot) become
dataclasses. Schedule warnings are polymorphic typed dictionaries constructed
inside the planner engine.

Dashboard selector resolution is union (logical OR): a substance belongs when it
carries at least one declared category/term selector.

Substance carries generic ontology assertion records.  Axis/category names are
owned by generated ontology metadata, not by this runtime contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple, TypedDict

type SlotNear = str
type RelationType = str
type Severity = str
type ConcernKind = str
type ResearchState = str


@dataclass(frozen=True, slots=True)
class Concern:
    kind: ConcernKind
    text: str


@dataclass(frozen=True, slots=True)
class ConcernRecord:
    """A concern projected from any authored subject card.

    Concerns are annotations only.  The subject identity is retained so
    presentation code can explain where the authored text came from, while
    the scheduler never needs to inspect this record.
    """

    subject_kind: str
    subject_id: str
    concern_kind: ConcernKind
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
class KnowledgeAssertion:
    category: str
    value: str
    research_state: ResearchState = "unassessed"
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Substance:
    id: str
    name: str
    knowledge_assertions: tuple[KnowledgeAssertion, ...] = ()
    form: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    concerns: tuple[Concern, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductComponent:
    substance: str
    id: str
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
    concerns: tuple[Concern, ...] = ()
    use_pattern: str | None = None


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
    id: str
    name: str
    description: str
    selectors: tuple[RelationSelector, ...]
    declares_context: tuple[str, ...] = ()
    benefit: DashboardBenefit | None = None
    risk: DashboardRisk | None = None
    # Provenance only: this path is never used for dashboard identity or
    # equality.  Authored ``id`` is the sole semantic identity.
    source_path: Path | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class RelationSelector:
    """A canonical endpoint: exactly one entity or category/term pair.

    ``scope`` is retained only as raw relation evidence metadata.
    """

    entity_id: str | None = None
    entity_name: str | None = None
    category: str | None = None
    term: str | None = None
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class OntologyAssertion:
    """A non-blocking semantic assertion projected from canonical ontology."""

    id: str
    relation_type: RelationType
    assertion_kind: str
    semantic_family: str
    reason: str
    source_selector: RelationSelector
    target_selector: RelationSelector
    action: str | None = None
    severity: Severity | None = None
    research_state: ResearchState = "unassessed"
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Relation:
    id: str
    type: RelationType
    reason: str
    source_selector: RelationSelector
    target_selector: RelationSelector
    action: str | None = None
    severity: Severity | None = None
    assertion_kind: str | None = None
    semantic_family: str | None = None
    research_state: ResearchState = "unassessed"
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Slot:
    """One pillbox slot, post-flatten.

    The pillbox and pillbox_label fields are joined in by load_pillboxes. The stack
    field is the explicit authored pillbox-to-stack reference.
    """

    slot_id: str
    label: str
    order: int
    pillbox: str
    pillbox_label: str
    stack: str
    anchors: Mapping[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Pillbox:
    name: str
    label: str
    stack: str
    # key = slot_id; values are flattened Slot instances joined with pillbox metadata at load time.
    slots: dict[str, Slot]


class FindResult(NamedTuple):
    score: float
    card_id: str
    label: str
    path: Path
