"""Typed records for generated schedule and review output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict, cast

if TYPE_CHECKING:
    from planner.canonical_optimizer_result import Optimal
    from planner.contracts import Slot
    from planner.ontology.canonical_inference import Success

ProductTrackingState = str
UsageState = str
type PlacementBasis = Literal["pressure_evidence", "balance_and_tie_break_only"]


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
    placement_groups: dict[str, list[str]]


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
    placement_basis: PlacementBasis
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


_DOCUMENT_FIELDS = frozenset(CanonicalScheduleData.__annotations__)
_PRESSURE_MATCH_FIELDS = frozenset(CanonicalPressureMatch.__annotations__)
_DOMAIN_LOAD_FIELDS = frozenset(CanonicalDomainLoadProof.__annotations__)
_EXPLANATION_FIELDS = frozenset(CanonicalPlacementExplanation.__annotations__)


@dataclass(frozen=True, slots=True)
class _ProofExpectations:
    pressure_matches: Mapping[tuple[str, str, str], CanonicalPressureMatch]
    result: Optimal


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
        _validate_publication_inputs(self.result, self.inference, self.slots)
        document = _validate_document_shape(self.document)
        assignments = _validate_assignments(document, self.result, self.slots)
        _validate_objective(document, self.result)
        _validate_canonical_proof_fields(document, assignments, self.inference, self.slots, self.result)


def _validate_publication_inputs(result: object, inference: object, slots: object) -> None:
    from planner.canonical_optimizer_result import Optimal
    from planner.ontology.canonical_inference import Success

    if not isinstance(result, Optimal):
        raise TypeError("only an Optimal optimizer result can be published")
    if not isinstance(inference, Success):
        raise TypeError("canonical publication requires successful inference")
    if not isinstance(slots, Mapping):
        raise TypeError("canonical publication slots must be a mapping")


def _validate_document_shape(document: object) -> CanonicalScheduleData:
    if not isinstance(document, dict):
        raise TypeError("publication document must be a schedule mapping")
    typed_document = cast(dict[str, object], document)
    if set(typed_document) != _DOCUMENT_FIELDS:
        unexpected = sorted(set(typed_document).symmetric_difference(_DOCUMENT_FIELDS))
        raise ValueError(f"canonical publication has missing or non-canonical fields: {unexpected}")
    if typed_document.get("status") != "Optimal":
        raise ValueError("publication document must declare status Optimal")
    return cast(CanonicalScheduleData, typed_document)


def _validate_assignments(
    document: CanonicalScheduleData, result: Optimal, slots: Mapping[str, Slot]
) -> dict[str, str]:
    assignments = document["assignments"]
    if not isinstance(assignments, dict) or assignments != result.assignments:
        raise ValueError("publication assignments do not match the proved optimizer result")
    if set(assignments.values()) - set(slots):
        raise ValueError("publication assignments reference an unknown slot")
    return assignments


def _validate_objective(document: CanonicalScheduleData, result: Optimal) -> None:
    expected_objective = {
        "satisfied_pressures": result.objective.satisfied_pressures,
        "squared_load": result.objective.squared_load,
        "assignment_key": result.objective.assignment_key,
    }
    if document["objective"] != expected_objective:
        raise ValueError("publication objective does not match the proved optimizer result")


def _validate_canonical_proof_fields(
    document: CanonicalScheduleData,
    assignments: dict[str, str],
    inference: Success,
    slots: Mapping[str, Slot],
    result: Optimal,
) -> None:
    expectations = _ProofExpectations(
        pressure_matches={
            (pressure.item_id, pressure.dimension, pressure.value): _expected_pressure_match(
                pressure, slots[assignments[pressure.item_id]]
            )
            for pressure in inference.pressures
        },
        result=result,
    )
    actual_matches = _validate_pressure_matches(
        document["pressure_matches"], assignments, expectations.pressure_matches
    )
    if sum(match["satisfied"] for match in actual_matches.values()) != result.objective.satisfied_pressures:
        raise ValueError("canonical pressure satisfaction does not match the proved objective")
    _validate_domain_loads(document["domain_loads"], assignments, slots, result, document["objective"])
    _validate_optimizer_proof(document["optimizer_proof"], result)
    _validate_placement_explanations(document["canonical_explanations"], assignments, slots, expectations)


def _validate_pressure_matches(
    pressure_matches: object,
    assignments: Mapping[str, str],
    expected_matches: Mapping[tuple[str, str, str], CanonicalPressureMatch],
) -> dict[tuple[str, str, str], CanonicalPressureMatch]:
    if not isinstance(pressure_matches, list):
        raise TypeError("canonical pressure_matches must be a list")
    typed_pressure_matches = cast(list[object], pressure_matches)
    actual_matches: dict[tuple[str, str, str], CanonicalPressureMatch] = {}
    for match in typed_pressure_matches:
        typed_match = _validate_pressure_match(match, assignments)
        identity = (typed_match["item_id"], typed_match["dimension"], typed_match["value"])
        _validate_pressure_identity(identity)
        if identity in actual_matches:
            raise ValueError("canonical pressure matches must have unique typed identities")
        actual_matches[identity] = typed_match
    if actual_matches != expected_matches:
        raise ValueError("canonical pressure proof does not exactly match successful inference")
    return actual_matches


def _validate_pressure_match(match: object, assignments: Mapping[str, str]) -> CanonicalPressureMatch:
    if not isinstance(match, dict):
        raise TypeError("canonical pressure match must be a mapping")
    typed_match = cast(dict[str, object], match)
    if set(typed_match) != _PRESSURE_MATCH_FIELDS:
        raise ValueError("canonical pressure match is missing typed proof fields")
    _validate_pressure_assignment(typed_match, assignments)
    _validate_pressure_state(typed_match)
    _validate_identifier_lists(typed_match)
    _validate_provenance_refs(typed_match["provenance_refs"])
    return cast(CanonicalPressureMatch, typed_match)


def _validate_pressure_identity(identity: tuple[str, str, str]) -> None:
    if not all(isinstance(value, str) and value for value in identity):
        raise ValueError("canonical pressure matches must have unique typed identities")


def _validate_pressure_assignment(match: Mapping[str, object], assignments: Mapping[str, str]) -> None:
    item_id = match["item_id"]
    if not isinstance(item_id, str) or item_id not in assignments or match["slot_id"] != assignments[item_id]:
        raise ValueError("canonical pressure match slot does not match the proved assignment")


def _validate_pressure_state(match: Mapping[str, object]) -> None:
    if not isinstance(match["slot_anchor"], (str, type(None))) or not isinstance(match["satisfied"], bool):
        raise TypeError("canonical pressure match anchor/state is malformed")


def _validate_identifier_lists(match: Mapping[str, object]) -> None:
    for field in ("fact_ids", "law_ids", "applicability_role_ids"):
        values = match[field]
        if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"canonical pressure match {field} must contain typed IDs")


def _validate_provenance_refs(provenance: object) -> None:
    if not isinstance(provenance, list) or not provenance:
        raise ValueError("canonical pressure match must retain provenance references")
    for ref in cast(list[object], provenance):
        _validate_provenance_ref(ref)


def _validate_provenance_ref(ref: object) -> None:
    if not isinstance(ref, dict):
        raise ValueError("canonical provenance reference is malformed")
    typed_ref = cast(dict[str, object], ref)
    if set(typed_ref) != {"source", "locator", "quotation"}:
        raise ValueError("canonical provenance reference is malformed")
    if not isinstance(typed_ref["source"], str) or not isinstance(typed_ref["locator"], str):
        raise ValueError("canonical provenance reference is malformed")
    if not isinstance(typed_ref["quotation"], (str, type(None))):
        raise ValueError("canonical provenance quotation is malformed")


def _validate_domain_loads(
    domain_loads: object,
    assignments: Mapping[str, str],
    slots: Mapping[str, Slot],
    result: Optimal,
    objective: CanonicalObjective,
) -> None:
    if not isinstance(domain_loads, dict):
        raise TypeError("canonical domain_loads must be a mapping")
    typed_domain_loads = cast(dict[str, object], domain_loads)
    expected_domains = {slots[slot_id].stack for slot_id in assignments.values()}
    if set(typed_domain_loads) != expected_domains:
        raise ValueError("canonical domain loads do not cover exactly the assignment domains")
    squared_loads: list[int] = []
    for domain, row in typed_domain_loads.items():
        _validate_domain_load(domain, row, assignments, slots, result)
        squared_loads.append(cast(int, cast(Mapping[str, object], row)["squared_load"]))
    if sum(squared_loads) != objective["squared_load"]:
        raise ValueError("canonical domain loads do not match the proved objective")


def _validate_domain_load(
    domain: object, row: object, assignments: Mapping[str, str], slots: Mapping[str, Slot], result: Optimal
) -> None:
    typed_domain, typed_row = _validate_domain_row(domain, row)
    expected_loads = _expected_domain_loads(typed_domain, assignments, slots)
    _validate_domain_load_values(typed_row, expected_loads)
    _validate_domain_proof(typed_row, typed_domain, result)


def _validate_domain_row(domain: object, row: object) -> tuple[str, Mapping[str, object]]:
    if not isinstance(domain, str) or not isinstance(row, dict):
        raise ValueError("canonical domain proof is incomplete")
    typed_row = cast(dict[str, object], row)
    if set(typed_row) != _DOMAIN_LOAD_FIELDS:
        raise ValueError("canonical domain proof is incomplete")
    return domain, typed_row


def _expected_domain_loads(domain: str, assignments: Mapping[str, str], slots: Mapping[str, Slot]) -> dict[str, int]:
    return {
        slot_id: sum(assigned_slot_id == slot_id for assigned_slot_id in assignments.values())
        for slot_id, slot in slots.items()
        if slot.stack == domain
    }


def _validate_domain_load_values(row: Mapping[str, object], expected_loads: Mapping[str, int]) -> None:
    loads = row["slot_loads"]
    if not isinstance(loads, dict):
        raise ValueError("canonical domain slot loads are malformed")
    typed_loads = cast(dict[str, object], loads)
    if not all(_is_valid_slot_load(slot_id, load) for slot_id, load in typed_loads.items()):
        raise ValueError("canonical domain slot loads are malformed")
    squared_load = row["squared_load"]
    if not isinstance(squared_load, int) or isinstance(squared_load, bool) or squared_load < 0:
        raise ValueError("canonical domain squared load is malformed")
    if typed_loads != expected_loads or squared_load != sum(load * load for load in expected_loads.values()):
        raise ValueError("canonical domain load does not match the proved assignment")


def _validate_domain_proof(row: Mapping[str, object], domain: str, result: Optimal) -> None:
    expected_proof = _domain_proof(domain, result)
    if not isinstance(row["proof"], list) or not row["proof"] or row["proof"] != expected_proof:
        raise ValueError("canonical domain optimizer proof is malformed")


def _is_valid_slot_load(slot_id: object, load: object) -> bool:
    return isinstance(slot_id, str) and isinstance(load, int) and not isinstance(load, bool) and load >= 0


def _domain_proof(domain: str, result: Optimal) -> list[str]:
    return [proof for proof in result.proofs if proof.startswith(f"domain={domain!r} ")]


def _validate_optimizer_proof(optimizer_proof: object, result: Optimal) -> None:
    if not isinstance(optimizer_proof, list) or optimizer_proof != list(result.proofs):
        raise ValueError("canonical optimizer proof is malformed")


def _validate_placement_explanations(
    explanations: object,
    assignments: Mapping[str, str],
    slots: Mapping[str, Slot],
    expectations: _ProofExpectations,
) -> None:
    if not isinstance(explanations, dict):
        raise ValueError("canonical placement explanations do not cover the proved assignments")
    typed_explanations = cast(dict[str, object], explanations)
    if set(typed_explanations) != set(assignments):
        raise ValueError("canonical placement explanations do not cover the proved assignments")
    for item_id, explanation in typed_explanations.items():
        _validate_placement_explanation(item_id, explanation, assignments, slots, expectations)


def _validate_placement_explanation(
    item_id: object,
    explanation: object,
    assignments: Mapping[str, str],
    slots: Mapping[str, Slot],
    expectations: _ProofExpectations,
) -> None:
    typed_explanation = _validate_explanation_identity(item_id, explanation)
    if not isinstance(item_id, str) or typed_explanation["slot_id"] != assignments[item_id]:
        raise ValueError("canonical placement explanation does not match the proved assignment")
    slot = slots[assignments[item_id]]
    _validate_explanation_anchors(typed_explanation, slot)
    _validate_explanation_proofs(typed_explanation, item_id, slot, expectations)


def _validate_explanation_identity(item_id: object, explanation: object) -> Mapping[str, object]:
    if not isinstance(explanation, dict):
        raise ValueError("canonical placement explanation has an invalid item identity")
    typed_explanation = cast(dict[str, object], explanation)
    if set(typed_explanation) != _EXPLANATION_FIELDS:
        raise ValueError("canonical placement explanation has an invalid item identity")
    if typed_explanation["item_id"] != item_id:
        raise ValueError("canonical placement explanation has an invalid item identity")
    return typed_explanation


def _validate_explanation_anchors(explanation: Mapping[str, object], slot: Slot) -> None:
    if explanation["slot_anchors"] != _slot_anchors(slot):
        raise ValueError("canonical placement explanation is missing slot anchors")


def _validate_explanation_proofs(
    explanation: Mapping[str, object], item_id: str, slot: Slot, expectations: _ProofExpectations
) -> None:
    expected_item_matches = [
        match for identity, match in expectations.pressure_matches.items() if identity[0] == item_id
    ]
    expected_basis: PlacementBasis = "pressure_evidence" if expected_item_matches else "balance_and_tie_break_only"
    if explanation["placement_basis"] != expected_basis:
        raise ValueError("canonical placement explanation has an invalid placement basis")
    if explanation["pressure_matches"] != expected_item_matches or explanation["optimizer_proof"] != _domain_proof(
        slot.stack, expectations.result
    ):
        raise ValueError("canonical placement explanation is missing proof records")


def _slot_anchors(slot: Slot) -> dict[str, str | None]:
    return {
        "meal_context": slot.meal_context,
        "circadian_anchor": slot.circadian_anchor,
        "exercise_anchor": slot.exercise_anchor,
    }


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
