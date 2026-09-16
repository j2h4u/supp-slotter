"""Pure projections used exclusively by the solver-owned schedule writer."""

from __future__ import annotations

from collections.abc import Mapping

from planner.canonical_optimizer_result import Optimal
from planner.contracts import Product, Slot
from planner.ontology.canonical_inference import NormalizedUnaryPressure
from planner.ontology.runtime_program import IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY
from planner.schedule_types import (
    CanonicalDomainLoadProof,
    CanonicalPlacementExplanation,
    CanonicalPressureMatch,
    CanonicalProvenanceRef,
    CanonicalPublicationSource,
    CanonicalScheduleData,
    SchedulePillbox,
    ScheduleProductEntry,
)


def _format_product_name(product: Product) -> str:
    name = product.name or product.id or "unknown product"
    return f"{product.brand} - {name}" if product.brand and product.brand != "unknown" else name


def build_canonical_schedule_document(source: CanonicalPublicationSource, result: Optimal) -> CanonicalScheduleData:
    """Derive the whole schedule document from an immutable source and proof."""
    assignments = dict(sorted(result.assignments.items()))
    if set(assignments) != set(source.item_domains):
        raise ValueError("canonical optimizer did not assign exactly the publication items")
    if any(slot_id not in source.slots for slot_id in assignments.values()):
        raise ValueError("canonical optimizer assignment references an unknown slot")
    if any(source.slots[slot_id].stack != source.item_domains[item_id] for item_id, slot_id in assignments.items()):
        raise ValueError("canonical optimizer assignment crosses a scheduling domain")
    matches = _pressure_matches(source, assignments)
    if sum(match["satisfied"] for match in matches) != result.objective.satisfied_pressures:
        raise ValueError("canonical pressure matches do not match the proved objective")
    domain_loads = _domain_loads(source.slots, assignments, result)
    if sum(row["squared_load"] for row in domain_loads.values()) != result.objective.squared_load:
        raise ValueError("canonical domain loads do not match the proved objective")
    explanations = _explanations(source.slots, assignments, matches, result)
    return {
        "status": "Optimal",
        "objective": {
            "satisfied_pressures": result.objective.satisfied_pressures,
            "squared_load": result.objective.squared_load,
            "assignment_key": result.objective.assignment_key,
        },
        "assignments": assignments,
        "pressure_matches": matches,
        "domain_loads": domain_loads,
        "optimizer_proof": list(result.proofs),
        "canonical_explanations": explanations,
        "summary": {"placement_groups": _presentation_groups(source, assignments)},
        "pillboxes": _pillboxes(source, assignments),
    }


def _pressure_matches(
    source: CanonicalPublicationSource, assignments: Mapping[str, str]
) -> list[CanonicalPressureMatch]:
    matches = [
        _pressure_match(
            pressure,
            source.slots[assignments[pressure.item_id]],
            source.pressure_satisfaction_strategy,
        )
        for pressure in source.inference.pressures
    ]
    return sorted(matches, key=lambda row: (row["item_id"], row["dimension"], row["value"]))


def _pressure_match(
    pressure: NormalizedUnaryPressure,
    slot: Slot,
    pressure_satisfaction_strategy: str,
) -> CanonicalPressureMatch:
    provenance: dict[tuple[str, str, str | None], CanonicalProvenanceRef] = {}
    for derivation in pressure.derivations:
        for ref in derivation.provenance:
            provenance[(ref.source, ref.locator, ref.quotation)] = {
                "source": ref.source,
                "locator": ref.locator,
                "quotation": ref.quotation,
            }
    anchor = slot.anchors[pressure.dimension]
    return {
        "item_id": pressure.item_id,
        "dimension": pressure.dimension,
        "value": pressure.value,
        "slot_id": slot.slot_id,
        "slot_anchor": anchor,
        "satisfied": _pressure_is_satisfied(anchor, pressure.value, pressure_satisfaction_strategy),
        "fact_ids": sorted({derivation.fact_id for derivation in pressure.derivations}),
        "law_ids": sorted({derivation.law_id for derivation in pressure.derivations}),
        "applicability_role_ids": sorted({
            derivation.path.role_id for derivation in pressure.derivations if derivation.path.role_id is not None
        }),
        "applicability_product_ids": sorted({derivation.path.product for derivation in pressure.derivations}),
        "provenance_refs": [
            provenance[key]
            for key in sorted(provenance, key=lambda row: (row[0], row[1], row[2] is not None, row[2] or ""))
        ],
    }


def _pressure_is_satisfied(anchor: str | None, value: str, pressure_satisfaction_strategy: str) -> bool:
    if pressure_satisfaction_strategy != IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY:
        raise ValueError("canonical output has an unsupported pressure satisfaction strategy")
    return anchor == value


def _domain_loads(
    slots: Mapping[str, Slot], assignments: Mapping[str, str], result: Optimal
) -> dict[str, CanonicalDomainLoadProof]:
    used_domains = sorted({slots[slot_id].stack for slot_id in assignments.values()})
    return {
        domain: {
            "slot_loads": {
                slot_id: sum(assigned == slot_id for assigned in assignments.values())
                for slot_id, slot in sorted(slots.items())
                if slot.stack == domain
            },
            "squared_load": sum(
                sum(assigned == slot_id for assigned in assignments.values()) ** 2
                for slot_id, slot in slots.items()
                if slot.stack == domain
            ),
            "proof": [proof for proof in result.proofs if proof.startswith(f"domain={domain!r} ")],
        }
        for domain in used_domains
    }


def _explanations(
    slots: Mapping[str, Slot],
    assignments: Mapping[str, str],
    matches: list[CanonicalPressureMatch],
    result: Optimal,
) -> dict[str, CanonicalPlacementExplanation]:
    return {
        item_id: {
            "item_id": item_id,
            "slot_id": slot_id,
            "placement_basis": "pressure_evidence"
            if any(row["satisfied"] for row in matches if row["item_id"] == item_id)
            else "balance_and_tie_break_only",
            "slot_anchors": dict(sorted(slots[slot_id].anchors.items())),
            "pressure_matches": [row for row in matches if row["item_id"] == item_id],
            "optimizer_proof": [
                proof for proof in result.proofs if proof.startswith(f"domain={slots[slot_id].stack!r} ")
            ],
        }
        for item_id, slot_id in assignments.items()
    }


def _pillboxes(source: CanonicalPublicationSource, assignments: Mapping[str, str]) -> dict[str, SchedulePillbox]:
    output: dict[str, SchedulePillbox] = {}
    for slot in sorted(source.slots.values(), key=lambda row: (row.pillbox, row.order, row.slot_id)):
        output.setdefault(slot.pillbox, {"label": slot.pillbox_label, "slots": {}})["slots"][slot.slot_id] = {
            "label": slot.label,
            "products": [],
        }
    for item_id, slot_id in assignments.items():
        product = source.products[source.item_products[item_id]]
        entry: ScheduleProductEntry = {"item_id": item_id, "label": _format_product_name(product)}
        output[source.slots[slot_id].pillbox]["slots"][slot_id]["products"].append(entry)
    for pillbox in output.values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"].sort(key=lambda row: (row["label"].casefold(), row["item_id"]))
    return output


def _presentation_groups(source: CanonicalPublicationSource, assignments: Mapping[str, str]) -> dict[str, list[str]]:
    episodic = sorted(
        item_id
        for item_id in assignments
        if source.products[source.item_products[item_id]].use_pattern == "not_every_day"
    )
    episodic_set = set(episodic)
    routine = sorted(item_id for item_id in assignments if item_id not in episodic_set)
    if set(routine) | episodic_set != set(assignments) or set(routine) & episodic_set:
        raise ValueError("presentation groups must partition all assignments")
    return {"routine": routine, "episodic": episodic}
