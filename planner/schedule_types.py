"""Typed records for generated schedule and review output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from planner.contracts import Slot
    from planner.engine._canonical_optimizer import Optimal
    from planner.ontology.canonical_inference import Success

ProductTrackingState = str
UsageState = str


class DashboardMatchedTrait(TypedDict):
    namespace: str
    slug: str


class DashboardRelevance(TypedDict):
    matched_traits: list[DashboardMatchedTrait]


class DashboardProductTracking(TypedDict):
    state: ProductTrackingState
    product_count: int


class DashboardUsage(TypedDict):
    state: UsageState
    stacks: list[str]


class DashboardProductPresence(TypedDict):
    product_count: int
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


class ScheduleWarning(TypedDict, total=False):
    type: str
    item: str
    product: str
    substance: str
    source_substance: str
    source_name: str
    target_substance: str
    target_name: str
    source: str
    target: str
    trait: str
    relation: str
    message: str
    reason: str
    action: str
    severity: str | int
    cluster: str
    active: list[str]
    concern: str
    category: str
    note: str
    candidate_items: list[str]
    source_matches: list[str]
    target_matches: list[str]
    presence: str
    show_matches: bool


class ScheduleSlotEntry(TypedDict):
    label: str
    products: list[str]
    substances: list[str]


class SchedulePillbox(TypedDict):
    label: str
    slots: dict[str, ScheduleSlotEntry]


class SchedulePlacementNote(TypedDict):
    product: str
    pillbox: str
    slot: str
    notes: list[str]


class ScheduleSummary(TypedDict):
    take: dict[str, list[str]]
    usage_groups: dict[str, list[str]]


class ActiveFactIndexEntry(TypedDict):
    namespace: str
    fact: str
    label: str
    product_count: int
    products: list[str]


class CanonicalObjective(TypedDict):
    """Exact objective values carried across the publication boundary."""

    satisfied_pressures: int
    squared_load: int
    assignment_key: tuple[tuple[int, str], ...]


class CanonicalProvenanceRef(TypedDict):
    """Typed source locator attached to a pressure derivation."""

    source: str
    locator: str
    quotation: str | None


class CanonicalPressureMatch(TypedDict):
    """One normalized pressure and the typed proof records supporting it."""

    item_id: str
    dimension: str
    value: str
    slot_id: str
    slot_anchor: str | None
    satisfied: bool
    fact_ids: list[str]
    law_ids: list[str]
    applicability_role_ids: list[str]
    provenance_refs: list[CanonicalProvenanceRef]


class CanonicalDomainLoadProof(TypedDict):
    """Per-independent-domain exact load and optimizer proof."""

    slot_loads: dict[str, int]
    squared_load: int
    proof: list[str]


class CanonicalPlacementExplanation(TypedDict):
    """Structured canonical placement explanation with no authored prose."""

    item_id: str
    slot_id: str
    slot_anchors: dict[str, str | None]
    pressure_matches: list[CanonicalPressureMatch]
    optimizer_proof: list[str]


class CanonicalScheduleData(TypedDict):
    """Closed generated document accepted by the canonical writer.

    Legacy pairwise journals and policy/vote explanations are intentionally
    not fields of this type.  Presentation sections remain inert projections;
    canonical authority lives only in the typed result/proof fields above.
    """

    status: Literal["Optimal"]
    objective: CanonicalObjective
    assignments: dict[str, str]
    pressure_matches: list[CanonicalPressureMatch]
    domain_loads: dict[str, CanonicalDomainLoadProof]
    optimizer_proof: list[str]
    canonical_explanations: dict[str, CanonicalPlacementExplanation]
    summary: ScheduleSummary
    placement_notes: list[SchedulePlacementNote]
    pillboxes: dict[str, SchedulePillbox]
    benefits: list[DashboardReviewEntryWithMembers]
    risks: list[DashboardReviewEntryWithMembers]
    warnings: list[ScheduleWarning]
    active_fact_index: list[ActiveFactIndexEntry]


@dataclass(frozen=True, slots=True)
class OptimalPublication:
    """Closed handoff from a proved optimizer result to a schedule document.

    Runtime checks are intentional: a type annotation alone cannot stop an
    ``Indeterminate`` result or a legacy schedule dictionary from crossing the
    publication boundary.
    """

    result: Optimal
    inference: Success
    slots: Mapping[str, Slot]
    document: CanonicalScheduleData

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Prove that this document is the exact projection of its inputs.

        The writer invokes this again immediately before rendering.  That is
        deliberate: TypedDict values remain mutable after construction, so a
        one-time constructor check is not a sufficient publication boundary.
        """
        # Import lazily: planner.engine is a re-exporting package and imports
        # legacy output modules that themselves depend on these TypedDicts.
        from planner.engine._canonical_optimizer import Optimal as _Optimal
        from planner.ontology.canonical_inference import Success as _Success

        if not isinstance(self.result, _Optimal):
            raise TypeError("only an Optimal optimizer result can be published")
        if not isinstance(self.inference, _Success):
            raise TypeError("canonical publication requires successful inference")
        if not isinstance(self.slots, Mapping):
            raise TypeError("canonical publication slots must be a mapping")
        if not isinstance(self.document, dict):
            raise TypeError("publication document must be a schedule mapping")
        required = {
            "status",
            "objective",
            "assignments",
            "pressure_matches",
            "domain_loads",
            "optimizer_proof",
            "canonical_explanations",
            "summary",
            "placement_notes",
            "pillboxes",
            "benefits",
            "risks",
            "warnings",
            "active_fact_index",
        }
        if set(self.document) != required:
            unexpected = sorted(set(self.document).symmetric_difference(required))
            raise ValueError(f"canonical publication has missing or non-canonical fields: {unexpected}")
        if self.document.get("status") != "Optimal":
            raise ValueError("publication document must declare status Optimal")
        assignments = self.document["assignments"]
        if not isinstance(assignments, dict) or assignments != self.result.assignments:
            raise ValueError("publication assignments do not match the proved optimizer result")
        if set(assignments.values()) - set(self.slots):
            raise ValueError("publication assignments reference an unknown slot")
        objective = self.document["objective"]
        expected_objective = {
            "satisfied_pressures": self.result.objective.satisfied_pressures,
            "squared_load": self.result.objective.squared_load,
            "assignment_key": self.result.objective.assignment_key,
        }
        if objective != expected_objective:
            raise ValueError("publication objective does not match the proved optimizer result")
        _validate_canonical_proof_fields(self.document, assignments, self.inference, self.slots, self.result)


def _validate_canonical_proof_fields(  # noqa: C901, PLR0912, PLR0914, PLR0915
    document: CanonicalScheduleData,
    assignments: dict[str, str],
    inference: Success,
    slots: Mapping[str, Slot],
    result: Optimal,
) -> None:
    expected_matches = {
        (pressure.item_id, pressure.dimension, pressure.value): _expected_pressure_match(
            pressure, slots[assignments[pressure.item_id]]
        )
        for pressure in inference.pressures
    }
    pressure_matches = document["pressure_matches"]
    if not isinstance(pressure_matches, list):
        raise TypeError("canonical pressure_matches must be a list")
    actual_matches: dict[tuple[str, str, str], CanonicalPressureMatch] = {}
    for match in pressure_matches:
        if not isinstance(match, dict):
            raise TypeError("canonical pressure match must be a mapping")
        required = {
            "item_id",
            "dimension",
            "value",
            "slot_id",
            "slot_anchor",
            "satisfied",
            "fact_ids",
            "law_ids",
            "applicability_role_ids",
            "provenance_refs",
        }
        if set(match) != required:
            raise ValueError("canonical pressure match is missing typed proof fields")
        item_id = match["item_id"]
        identity = (item_id, match["dimension"], match["value"])
        if not all(isinstance(value, str) and value for value in identity) or identity in actual_matches:
            raise ValueError("canonical pressure matches must have unique typed identities")
        if item_id not in assignments or match["slot_id"] != assignments[item_id]:
            raise ValueError("canonical pressure match slot does not match the proved assignment")
        if not isinstance(match["slot_anchor"], (str, type(None))) or not isinstance(match["satisfied"], bool):
            raise TypeError("canonical pressure match anchor/state is malformed")
        for field in ("fact_ids", "law_ids", "applicability_role_ids"):
            values = match[field]
            if (
                not isinstance(values, list)
                or not values
                or not all(isinstance(value, str) and value for value in values)
            ):
                raise ValueError(f"canonical pressure match {field} must contain typed IDs")
        provenance = match["provenance_refs"]
        if not isinstance(provenance, list) or not provenance:
            raise ValueError("canonical pressure match must retain provenance references")
        for ref in provenance:
            if not isinstance(ref, dict) or set(ref) != {"source", "locator", "quotation"}:
                raise ValueError("canonical provenance reference is malformed")
            if not isinstance(ref["source"], str) or not isinstance(ref["locator"], str):
                raise ValueError("canonical provenance reference is malformed")
            if not isinstance(ref["quotation"], (str, type(None))):
                raise ValueError("canonical provenance quotation is malformed")
        actual_matches[identity] = match
    if actual_matches != expected_matches:
        raise ValueError("canonical pressure proof does not exactly match successful inference")
    if sum(match["satisfied"] for match in actual_matches.values()) != result.objective.satisfied_pressures:
        raise ValueError("canonical pressure satisfaction does not match the proved objective")

    domain_loads = document["domain_loads"]
    if not isinstance(domain_loads, dict):
        raise TypeError("canonical domain_loads must be a mapping")
    expected_domains = {slots[slot_id].stack for slot_id in assignments.values()}
    if set(domain_loads) != expected_domains:
        raise ValueError("canonical domain loads do not cover exactly the assignment domains")
    for domain, row in domain_loads.items():
        if (
            not isinstance(domain, str)
            or not isinstance(row, dict)
            or set(row) != {"slot_loads", "squared_load", "proof"}
        ):
            raise ValueError("canonical domain proof is incomplete")
        loads = row["slot_loads"]
        if not isinstance(loads, dict) or not all(
            isinstance(slot_id, str) and isinstance(load, int) and not isinstance(load, bool) and load >= 0
            for slot_id, load in loads.items()
        ):
            raise ValueError("canonical domain slot loads are malformed")
        if not isinstance(row["squared_load"], int) or isinstance(row["squared_load"], bool) or row["squared_load"] < 0:
            raise ValueError("canonical domain squared load is malformed")
        expected_loads = {
            slot_id: sum(assigned_slot_id == slot_id for assigned_slot_id in assignments.values())
            for slot_id, slot in slots.items()
            if slot.stack == domain
        }
        expected_squared_load = sum(load * load for load in expected_loads.values())
        expected_proof = [proof for proof in result.proofs if proof.startswith(f"domain={domain!r} ")]
        if loads != expected_loads or row["squared_load"] != expected_squared_load:
            raise ValueError("canonical domain load does not match the proved assignment")
        if not isinstance(row["proof"], list) or not row["proof"] or row["proof"] != expected_proof:
            raise ValueError("canonical domain optimizer proof is malformed")
    if sum(row["squared_load"] for row in domain_loads.values()) != document["objective"]["squared_load"]:
        raise ValueError("canonical domain loads do not match the proved objective")

    optimizer_proof = document["optimizer_proof"]
    if not isinstance(optimizer_proof, list) or optimizer_proof != list(result.proofs):
        raise ValueError("canonical optimizer proof is malformed")
    explanations = document["canonical_explanations"]
    if not isinstance(explanations, dict) or set(explanations) != set(assignments):
        raise ValueError("canonical placement explanations do not cover the proved assignments")
    for item_id, explanation in explanations.items():
        if (
            not isinstance(explanation, dict)
            or set(explanation)
            != {
                "item_id",
                "slot_id",
                "slot_anchors",
                "pressure_matches",
                "optimizer_proof",
            }
            or explanation["item_id"] != item_id
        ):
            raise ValueError("canonical placement explanation has an invalid item identity")
        if explanation["slot_id"] != assignments[item_id]:
            raise ValueError("canonical placement explanation does not match the proved assignment")
        slot = slots[assignments[item_id]]
        expected_anchors = {
            "meal_context": slot.meal_context,
            "circadian_anchor": slot.circadian_anchor,
            "exercise_anchor": slot.exercise_anchor,
        }
        if explanation["slot_anchors"] != expected_anchors:
            raise ValueError("canonical placement explanation is missing slot anchors")
        expected_item_matches = [match for identity, match in expected_matches.items() if identity[0] == item_id]
        expected_proof = [proof for proof in result.proofs if proof.startswith(f"domain={slot.stack!r} ")]
        if explanation["pressure_matches"] != expected_item_matches or explanation["optimizer_proof"] != expected_proof:
            raise ValueError("canonical placement explanation is missing proof records")


def _expected_pressure_match(pressure: object, slot: Slot) -> CanonicalPressureMatch:
    """Return the one closed document projection for a normalized pressure."""
    from planner.ontology.canonical_inference import NormalizedUnaryPressure

    if not isinstance(pressure, NormalizedUnaryPressure):
        raise TypeError("canonical inference contains an invalid pressure")
    provenance: dict[tuple[str, str, str | None], CanonicalProvenanceRef] = {}
    for derivation in pressure.derivations:
        for ref in derivation.provenance:
            provenance[(ref.source, ref.locator, ref.quotation)] = {
                "source": ref.source,
                "locator": ref.locator,
                "quotation": ref.quotation,
            }
    anchor = getattr(slot, pressure.dimension, None)
    return {
        "item_id": pressure.item_id,
        "dimension": pressure.dimension,
        "value": pressure.value,
        "slot_id": slot.slot_id,
        "slot_anchor": anchor,
        "satisfied": anchor == pressure.value,
        "fact_ids": sorted({derivation.fact_id for derivation in pressure.derivations}),
        "law_ids": sorted({derivation.law_id for derivation in pressure.derivations}),
        "applicability_role_ids": sorted({derivation.path.role_id for derivation in pressure.derivations}),
        "provenance_refs": [provenance[key] for key in sorted(provenance)],
    }


class DashboardReviewResult(TypedDict):
    benefits: list[DashboardReviewEntryWithMembers]
    risks: list[DashboardReviewEntryWithMembers]
    warnings: list[ScheduleWarning]
