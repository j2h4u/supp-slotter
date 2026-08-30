"""Canonical plan-command publication assembly."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from planner.cards.pillboxes import build_empty_schedule_pillboxes
from planner.cards.product import format_item_product_name
from planner.contracts import Pillbox, Product, Slot
from planner.engine._canonical_optimizer import Optimal
from planner.ontology.canonical_inference import NormalizedUnaryPressure, Success
from planner.schedule_types import (
    CanonicalDomainLoadProof,
    CanonicalPlacementExplanation,
    CanonicalPressureMatch,
    CanonicalProvenanceRef,
    CanonicalScheduleData,
    OptimalPublication,
    SchedulePillbox,
)


@dataclass(frozen=True, slots=True)
class CanonicalScheduleOutputInput:
    """Closed inputs for canonical output assembly."""

    result: Optimal
    slots: Mapping[str, Slot]
    inference: Success
    item_products: Mapping[str, str] = field(default_factory=dict)
    item_stacks: Mapping[str, str] = field(default_factory=dict)
    products: Mapping[str, Product] = field(default_factory=dict)
    pillboxes: Mapping[str, Pillbox] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _CanonicalScheduleParts:
    """Completed proof projections required by the closed schedule document."""

    assignments: dict[str, str]
    pressure_matches: list[CanonicalPressureMatch]
    domain_loads: dict[str, CanonicalDomainLoadProof]
    explanations: dict[str, CanonicalPlacementExplanation]
    pillboxes: dict[str, dict[str, object]]


def build_canonical_schedule_output(
    output_input: CanonicalScheduleOutputInput,
) -> OptimalPublication:
    """Build an in-memory publication from a proved canonical optimum."""
    slots, assignments = _validated_output_inputs(output_input)
    pressure_matches = _pressure_matches(output_input.inference, assignments, slots)
    _validate_satisfied_pressure_count(pressure_matches, output_input.result)
    domain_loads = _canonical_domain_loads(assignments, slots, output_input.result)
    _validate_squared_load(domain_loads, output_input.result)
    explanations = _canonical_explanations(assignments, slots, pressure_matches, output_input.result)
    pillboxes = _canonical_pillboxes(output_input.pillboxes, slots)
    _add_assigned_products(pillboxes, assignments, slots, output_input.item_products, output_input.products)
    parts = _CanonicalScheduleParts(
        assignments=assignments,
        pressure_matches=pressure_matches,
        domain_loads=domain_loads,
        explanations=explanations,
        pillboxes=pillboxes,
    )
    document = _canonical_document(output_input, parts)
    return OptimalPublication(output_input.result, output_input.inference, slots, document)


def _validated_output_inputs(
    output_input: CanonicalScheduleOutputInput,
) -> tuple[dict[str, Slot], dict[str, str]]:
    if not isinstance(output_input.result, Optimal):
        raise TypeError("canonical output requires an Optimal optimizer result")
    if not isinstance(output_input.inference, Success):
        raise TypeError("canonical output requires successful canonical inference")
    slots = dict(output_input.slots)
    assignments = dict(sorted(output_input.result.assignments.items()))
    if any(slot_id not in slots for slot_id in assignments.values()):
        raise ValueError("canonical optimizer assignment references an unknown slot")
    if any(pressure.item_id not in assignments for pressure in output_input.inference.pressures):
        raise ValueError("canonical pressure references an unassigned item")
    return slots, assignments


def _pressure_matches(
    inference: Success, assignments: Mapping[str, str], slots: Mapping[str, Slot]
) -> list[CanonicalPressureMatch]:
    matches = [
        _canonical_pressure_match(pressure, slots[assignments[pressure.item_id]]) for pressure in inference.pressures
    ]
    matches.sort(key=lambda row: (row["item_id"], row["dimension"], row["value"]))
    return matches


def _validate_satisfied_pressure_count(pressure_matches: list[CanonicalPressureMatch], result: Optimal) -> None:
    if sum(match["satisfied"] for match in pressure_matches) != result.objective.satisfied_pressures:
        raise ValueError("canonical pressure matches do not match the proved objective")


def _validate_squared_load(domain_loads: Mapping[str, CanonicalDomainLoadProof], result: Optimal) -> None:
    if sum(row["squared_load"] for row in domain_loads.values()) != result.objective.squared_load:
        raise ValueError("canonical domain loads do not match the proved objective")


def _canonical_explanations(
    assignments: Mapping[str, str],
    slots: Mapping[str, Slot],
    pressure_matches: list[CanonicalPressureMatch],
    result: Optimal,
) -> dict[str, CanonicalPlacementExplanation]:
    return {
        item_id: _canonical_placement_explanation(
            item_id,
            slot_id,
            slots[slot_id],
            [row for row in pressure_matches if row["item_id"] == item_id],
            result,
        )
        for item_id, slot_id in assignments.items()
    }


def _add_assigned_products(
    pillboxes: Mapping[str, dict[str, object]],
    assignments: Mapping[str, str],
    slots: Mapping[str, Slot],
    item_products: Mapping[str, str],
    products: Mapping[str, Product],
) -> None:
    for item_id, slot_id in assignments.items():
        slot = slots[slot_id]
        slot_map = cast(dict[str, dict[str, object]], pillboxes[slot.pillbox]["slots"])
        cast(list[str], slot_map[slot_id]["products"]).append(_canonical_product_name(item_id, item_products, products))
    _sort_pillbox_products(pillboxes)


def _sort_pillbox_products(pillboxes: Mapping[str, dict[str, object]]) -> None:
    for raw_pillbox in pillboxes.values():
        for raw_slot in cast(dict[str, dict[str, object]], raw_pillbox["slots"]).values():
            raw_slot["products"] = sorted(cast(list[str], raw_slot["products"]), key=str.casefold)


def _presentation_groups(
    assignments: Mapping[str, str],
    item_products: Mapping[str, str],
    item_stacks: Mapping[str, str],
    products: Mapping[str, Product],
) -> dict[str, list[str]]:
    episodic_items = _episodic_items(assignments, item_products, item_stacks, products)
    return {
        "routine": _routine_items(assignments, item_products, item_stacks, products, episodic_items),
        "episodic": [_canonical_product_name(item_id, item_products, products) for item_id in episodic_items],
    }


def _episodic_items(
    assignments: Mapping[str, str],
    item_products: Mapping[str, str],
    item_stacks: Mapping[str, str],
    products: Mapping[str, Product],
) -> list[str]:
    return sorted(
        item_id
        for item_id, product_id in item_products.items()
        if item_id in assignments
        and item_stacks.get(item_id) == "daily"
        and products.get(product_id) is not None
        and products[product_id].use_pattern == "not_every_day"
    )


def _routine_items(
    assignments: Mapping[str, str],
    item_products: Mapping[str, str],
    item_stacks: Mapping[str, str],
    products: Mapping[str, Product],
    episodic_items: list[str],
) -> list[str]:
    return [
        _canonical_product_name(item_id, item_products, products)
        for item_id, product_id in sorted(item_products.items())
        if item_stacks.get(item_id) == "daily"
        and item_id not in episodic_items
        and products.get(product_id) is not None
        and products[product_id].use_pattern != "not_every_day"
    ]


def _canonical_document(
    output_input: CanonicalScheduleOutputInput,
    parts: _CanonicalScheduleParts,
) -> CanonicalScheduleData:
    objective = output_input.result.objective
    return {
        "status": "Optimal",
        "objective": {
            "satisfied_pressures": objective.satisfied_pressures,
            "squared_load": objective.squared_load,
            "assignment_key": objective.assignment_key,
        },
        "assignments": parts.assignments,
        "pressure_matches": parts.pressure_matches,
        "domain_loads": parts.domain_loads,
        "optimizer_proof": list(output_input.result.proofs),
        "canonical_explanations": parts.explanations,
        "summary": {
            "placement_groups": _presentation_groups(
                parts.assignments,
                output_input.item_products,
                output_input.item_stacks,
                output_input.products,
            ),
        },
        "placement_notes": [],
        "pillboxes": cast(dict[str, SchedulePillbox], parts.pillboxes),
        "benefits": [],
        "risks": [],
        "warnings": [],
        "active_fact_index": [],
    }


def _canonical_product_name(item_id: str, item_products: Mapping[str, str], products: Mapping[str, Product]) -> str:
    product_id = item_products.get(item_id, item_id)
    product = products.get(product_id)
    return format_item_product_name(item_id, dict(item_products), dict(products)) if product is not None else product_id


def _canonical_pillboxes(pillboxes: Mapping[str, Pillbox], slots: Mapping[str, Slot]) -> dict[str, dict[str, object]]:
    if pillboxes:
        return cast(dict[str, dict[str, object]], build_empty_schedule_pillboxes(dict(pillboxes)))
    grouped: dict[str, dict[str, object]] = {}
    for slot in sorted(slots.values(), key=lambda row: (row.pillbox, row.order, row.slot_id)):
        pillbox = grouped.setdefault(slot.pillbox, {"label": slot.pillbox_label, "slots": {}})
        cast(dict[str, dict[str, object]], pillbox["slots"])[slot.slot_id] = {
            "label": slot.label,
            "products": [],
            "substances": [],
        }
    return grouped


def _canonical_pressure_match(pressure: NormalizedUnaryPressure, slot: Slot) -> CanonicalPressureMatch:
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


def _canonical_domain_loads(
    assignments: Mapping[str, str], slots: Mapping[str, Slot], result: Optimal
) -> dict[str, CanonicalDomainLoadProof]:
    by_domain: dict[str, list[str]] = {}
    for slot_id in assignments.values():
        by_domain.setdefault(slots[slot_id].stack, []).append(slot_id)
    proofs = {
        domain: [proof for proof in result.proofs if proof.startswith(f"domain={domain!r} ")] for domain in by_domain
    }
    domain_loads: dict[str, CanonicalDomainLoadProof] = {}
    for domain in sorted(by_domain):
        domain_slot_ids = sorted(slot_id for slot_id, slot in slots.items() if slot.stack == domain)
        loads = {slot_id: sum(assigned == slot_id for assigned in assignments.values()) for slot_id in domain_slot_ids}
        domain_loads[domain] = {
            "slot_loads": loads,
            "squared_load": sum(load * load for load in loads.values()),
            "proof": proofs[domain],
        }
    return domain_loads


def _canonical_placement_explanation(
    item_id: str,
    slot_id: str,
    slot: Slot,
    pressure_matches: list[CanonicalPressureMatch],
    result: Optimal,
) -> CanonicalPlacementExplanation:
    return {
        "item_id": item_id,
        "slot_id": slot_id,
        "placement_basis": "pressure_evidence" if pressure_matches else "balance_and_tie_break_only",
        "slot_anchors": {
            "meal_context": slot.meal_context,
            "circadian_anchor": slot.circadian_anchor,
            "exercise_anchor": slot.exercise_anchor,
        },
        "pressure_matches": pressure_matches,
        "optimizer_proof": [proof for proof in result.proofs if proof.startswith(f"domain={slot.stack!r} ")],
    }
