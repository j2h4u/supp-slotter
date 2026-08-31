"""Typed records at the canonical publication boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, TypedDict

from planner.contracts import Product, Slot
from planner.ontology.canonical_inference import Success

if TYPE_CHECKING:
    from planner.canonical_optimizer_result import Optimal

type PlacementBasis = Literal["pressure_evidence", "balance_and_tie_break_only"]
type ProductTrackingState = str


class DashboardMatchedTrait(TypedDict):
    namespace: str
    slug: str


class DashboardRelevance(TypedDict):
    matched_traits: list[DashboardMatchedTrait]


class DashboardProductTracking(TypedDict):
    state: str
    product_count: int


class DashboardProductPresence(TypedDict):
    product_count: int
    stacks: list[str]


class DashboardUsage(TypedDict):
    state: str
    stacks: list[str]


class DashboardMember(TypedDict):
    substance_id: str
    substance: str
    relevance: DashboardRelevance
    product_tracking: DashboardProductTracking
    usage: DashboardUsage


class DashboardReviewEntry(TypedDict):
    id: str
    name: str
    declares_context: list[str]
    declares_context_labels: list[str]


class DashboardReviewEntryWithMembers(DashboardReviewEntry, total=False):
    members: list[DashboardMember]


class DashboardReviewResult(TypedDict):
    """Review UX retains dashboard benefits and risks; schedules do not carry them."""

    benefits: list[DashboardReviewEntryWithMembers]
    risks: list[DashboardReviewEntryWithMembers]


class ScheduleProductEntry(TypedDict):
    item_id: str
    label: str


class ScheduleSlotEntry(TypedDict):
    label: str
    products: list[ScheduleProductEntry]


class SchedulePillbox(TypedDict):
    label: str
    slots: dict[str, ScheduleSlotEntry]


class ScheduleSummary(TypedDict):
    """A disjoint, complete partition of assigned item IDs."""

    placement_groups: dict[str, list[str]]


class CanonicalObjective(TypedDict):
    satisfied_pressures: int
    squared_load: int
    assignment_key: tuple[tuple[int, str], ...]


class CanonicalProvenanceRef(TypedDict):
    source: str
    locator: str
    quotation: str | None


class CanonicalPressureMatch(TypedDict):
    item_id: str
    dimension: str
    value: str
    slot_id: str
    slot_anchor: str | None
    satisfied: bool
    fact_ids: list[str]
    law_ids: list[str]
    applicability_role_ids: list[str]
    applicability_product_ids: list[str]
    provenance_refs: list[CanonicalProvenanceRef]


class CanonicalDomainLoadProof(TypedDict):
    slot_loads: dict[str, int]
    squared_load: int
    proof: list[str]


class CanonicalPlacementExplanation(TypedDict):
    item_id: str
    slot_id: str
    placement_basis: PlacementBasis
    slot_anchors: dict[str, str | None]
    pressure_matches: list[CanonicalPressureMatch]
    optimizer_proof: list[str]


class CanonicalScheduleData(TypedDict):
    """Generated schedule derived only by the solver-owned writer."""

    status: Literal["Optimal"]
    objective: CanonicalObjective
    assignments: dict[str, str]
    pressure_matches: list[CanonicalPressureMatch]
    domain_loads: dict[str, CanonicalDomainLoadProof]
    optimizer_proof: list[str]
    canonical_explanations: dict[str, CanonicalPlacementExplanation]
    summary: ScheduleSummary
    pillboxes: dict[str, SchedulePillbox]


def _frozen_slots(slots: Mapping[str, Slot]) -> Mapping[str, Slot]:
    copied: dict[str, Slot] = {}
    for slot_id, slot in sorted(slots.items()):
        if not isinstance(slot_id, str) or not slot_id or not isinstance(slot, Slot) or slot.slot_id != slot_id:
            raise ValueError("canonical publication slots must be keyed by their stable IDs")
        copied[slot_id] = Slot(
            slot.slot_id,
            slot.label,
            slot.order,
            slot.pillbox,
            slot.pillbox_label,
            slot.stack,
            MappingProxyType(dict(sorted(slot.anchors.items()))),
        )
    return MappingProxyType(copied)


def _validated_item_mappings(item_products: Mapping[str, str], item_domains: Mapping[str, str]) -> None:
    if set(item_products) != set(item_domains) or any(
        not isinstance(item_id, str)
        or not item_id
        or not isinstance(product_id, str)
        or not product_id
        or not isinstance(item_domains[item_id], str)
        or not item_domains[item_id]
        for item_id, product_id in item_products.items()
    ):
        raise ValueError("canonical publication item mappings must be exact and non-empty")


def _validated_dimensions(values: Mapping[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    dimensions = {key: frozenset(row) for key, row in values.items()}
    if not dimensions or any(
        not isinstance(key, str) or not key or not row or any(not isinstance(value, str) or not value for value in row)
        for key, row in dimensions.items()
    ):
        raise ValueError("canonical publication pressure metadata is invalid")
    return dimensions


@dataclass(frozen=True, slots=True)
class CanonicalPublicationSource:
    """Immutable answer-free snapshot accepted by schedule publication."""

    item_products: Mapping[str, str]
    item_domains: Mapping[str, str]
    slots: Mapping[str, Slot]
    inference: Success
    products: Mapping[str, Product]
    pressure_values_by_dimension: Mapping[str, frozenset[str]]
    pressure_satisfaction_strategy: str

    def __post_init__(self) -> None:
        item_products = dict(sorted(self.item_products.items()))
        item_domains = dict(sorted(self.item_domains.items()))
        products = dict(sorted(self.products.items()))
        if not isinstance(self.inference, Success):
            raise TypeError("canonical publication requires successful inference")
        _validated_item_mappings(item_products, item_domains)
        if any(
            not isinstance(product, Product) or product.id != product_id for product_id, product in products.items()
        ):
            raise ValueError("canonical publication products must be keyed by their stable IDs")
        if any(product_id not in products for product_id in item_products.values()):
            raise ValueError("canonical publication item references an unknown product")
        dimensions = _validated_dimensions(self.pressure_values_by_dimension)
        frozen_slots = _frozen_slots(self.slots)
        if any(set(slot.anchors) != set(dimensions) for slot in frozen_slots.values()):
            raise ValueError("canonical publication slots must carry every pressure dimension")
        for pressure in self.inference.pressures:
            if (
                pressure.item_id not in item_domains
                or pressure.dimension not in dimensions
                or pressure.value not in dimensions[pressure.dimension]
            ):
                raise ValueError("canonical publication inference is incompatible with its source mappings")
        object.__setattr__(self, "item_products", MappingProxyType(item_products))
        object.__setattr__(self, "item_domains", MappingProxyType(item_domains))
        object.__setattr__(self, "products", MappingProxyType(products))
        object.__setattr__(self, "slots", frozen_slots)
        object.__setattr__(self, "pressure_values_by_dimension", MappingProxyType(dimensions))


@dataclass(frozen=True, slots=True)
class PublishedSchedule:
    """A schedule installed after exact optimization and durable replacement."""

    document: CanonicalScheduleData
    result: Optimal
