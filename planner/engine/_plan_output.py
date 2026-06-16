"""Plan-command schedule.yaml assembly.

Extracted from `planner.engine.plan` to keep the scheduler module focused
on search + orchestration. This module owns the conversion from a solved
assignment dict into the full `schedule` dict that gets written to disk —
benefits/risks/warnings aggregation, pillbox population, explanations,
relation warnings, and humanize-rewrite of the raw warning stream.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from planner.cards.dashboards import build_dashboard_review
from planner.cards.pillboxes import build_empty_schedule_pillboxes
from planner.cards.product import (
    format_item_product_name,
)
from planner.cards.safety_warnings import collect_active_safety_concerns
from planner.cards.schedule import build_placement_notes, build_schedule_summary
from planner.cards.substance import format_substance_name
from planner.cards.traits import readable_traits
from planner.cards.warnings import humanize_warning, is_generic_manual_review_warning
from planner.contracts import Slot, StackEntry
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import build_substance_slot_names, explain_slot_choice
from planner.query_model import StackReadModel


class ScheduleOutputInput(NamedTuple):
    assignment: dict[str, str]
    slots: dict[str, Slot]
    active: ActiveIndex
    item_id_sequence: list[str]
    products: dict[str, Any]
    substances: dict[str, Any]
    trait_defs: dict[str, Any]
    prefer_pairs: set[frozenset[str]]
    stack_entries: dict[str, StackEntry]
    dashboard_files: list[Any]
    pillboxes: Any
    warnings_prefix: list[dict[str, Any]]
    read_model: StackReadModel


def build_schedule_output(
    output_input: ScheduleOutputInput,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the complete schedule dict from a solved assignment.

    Returns the schedule dict ready to be serialised (excluding the write step).
    """
    assignment = output_input.assignment
    slots = output_input.slots
    active = output_input.active
    item_id_sequence = output_input.item_id_sequence
    products = output_input.products
    substances = output_input.substances
    trait_defs = output_input.trait_defs
    prefer_pairs = output_input.prefer_pairs
    read_model = output_input.read_model
    schedule = _initial_schedule(output_input.pillboxes, assignment, active, products, prefer_pairs)
    _populate_pillbox_products(schedule, assignment, slots, active, item_id_sequence, products)
    _populate_pillbox_substances(schedule, assignment, slots, active, item_id_sequence, products, substances)

    active_substance_ids = {
        component_id for component_ids in active.active_components.values() for component_id in component_ids
    }
    cluster_review = build_dashboard_review(
        dashboard_files=output_input.dashboard_files,
        products=products,
        stack_entries=output_input.stack_entries,
        substances=substances,
    )
    schedule["benefits"] = cluster_review["benefits"]
    schedule["risks"] = cluster_review["risks"]
    schedule["warnings"].extend(cluster_review["warnings"])
    schedule["active_fact_index"] = read_model.active_fact_index(
        item_id_sequence=item_id_sequence,
        item_products=active.item_products,
    )

    _populate_explanations(schedule, output_input)
    _append_intra_product_relation_conflicts(schedule, active)

    schedule["warnings"].extend(
        collect_active_safety_concerns(
            active_order=item_id_sequence,
            active_components=active.active_components,
            item_products=active.item_products,
            products=products,
            substances=substances,
        )
    )
    schedule["warnings"].extend(output_input.warnings_prefix)
    _append_trait_warnings(schedule, active, trait_defs)
    _append_read_model_warnings(schedule, read_model, active_substance_ids)

    raw_warnings = list(schedule["warnings"])
    schedule["warnings"] = [
        humanize_warning(warning, products=products, substances=substances)
        for warning in schedule["warnings"]
        if not is_generic_manual_review_warning(warning)
    ]
    schedule["placement_notes"] = build_placement_notes(schedule)
    schedule["summary"] = build_schedule_summary(schedule)

    return schedule, raw_warnings


def _initial_schedule(
    pillboxes: Any,
    assignment: dict[str, str],
    active: ActiveIndex,
    products: dict[str, Any],
    prefer_pairs: set[frozenset[str]],
) -> dict[str, Any]:
    return {
        "summary": {},
        "placement_notes": [],
        "pillboxes": build_empty_schedule_pillboxes(pillboxes),
        "benefits": [],
        "risks": [],
        "warnings": [],
        "kept_together": [
            {
                "pair": sorted(
                    [format_item_product_name(item_id, active.item_products, products) for item_id in sorted(pair)],
                    key=str.casefold,
                ),
                "together": (assignment[sorted(pair)[0]] == assignment[sorted(pair)[1]]),
                "slot": assignment[sorted(pair)[0]]
                if assignment[sorted(pair)[0]] == assignment[sorted(pair)[1]]
                else None,
            }
            for pair in sorted(prefer_pairs, key=lambda item_pair: sorted(item_pair))
        ],
        "explanations": {},
    }


def _populate_pillbox_products(
    schedule: dict[str, Any],
    assignment: dict[str, str],
    slots: dict[str, Slot],
    active: ActiveIndex,
    item_id_sequence: list[str],
    products: dict[str, Any],
) -> None:
    for item_id in item_id_sequence:
        slot_name = assignment[item_id]
        pillbox_name = slots[slot_name].pillbox
        schedule["pillboxes"][pillbox_name]["slots"][slot_name]["products"].append(
            format_item_product_name(item_id, active.item_products, products)
        )
    for pillbox in schedule["pillboxes"].values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"] = sorted(slot_entry["products"], key=str.casefold)


def _populate_pillbox_substances(
    schedule: dict[str, Any],
    assignment: dict[str, str],
    slots: dict[str, Slot],
    active: ActiveIndex,
    item_id_sequence: list[str],
    products: dict[str, Any],
    substances: dict[str, Any],
) -> None:
    for slot_name, slot in slots.items():
        pillbox_name = slot.pillbox
        slot_entry = schedule["pillboxes"][pillbox_name]["slots"][slot_name]
        slot_item_ids = [item_id for item_id in item_id_sequence if assignment[item_id] == slot_name]
        slot_entry["substances"] = build_substance_slot_names(
            assigned_item_ids=slot_item_ids,
            item_products=active.item_products,
            products=products,
            substances=substances,
        )


def _populate_explanations(
    schedule: dict[str, Any],
    output_input: ScheduleOutputInput,
) -> None:
    for item_id in output_input.item_id_sequence:
        slot_name = output_input.assignment[item_id]
        slot = output_input.slots[slot_name]
        product_name = format_item_product_name(item_id, output_input.active.item_products, output_input.products)
        schedule["explanations"][product_name] = {
            "components": _component_names(output_input.active.active_components[item_id], output_input.substances),
            "pillbox": slot.pillbox,
            "slot": slot_name,
            "why_here": explain_slot_choice(output_input.active.item_traits[item_id], slot, output_input.trait_defs),
            "review_tags": readable_traits(output_input.active.item_traits[item_id], output_input.trait_defs),
        }


def _component_names(component_ids: list[str], substances: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for substance_id in component_ids:
        substance_dc = substances.get(substance_id)
        names.append(format_substance_name(substance_dc) if substance_dc is not None else substance_id)
    return names


def _append_intra_product_relation_conflicts(schedule: dict[str, Any], active: ActiveIndex) -> None:
    for relation_conflicts in active.intra_product_relation_conflicts_by_item.values():
        schedule["warnings"].extend(relation_conflicts)


def _append_trait_warnings(
    schedule: dict[str, Any],
    active: ActiveIndex,
    trait_defs: dict[str, Any],
) -> None:
    for item_id, traits in active.item_traits.items():
        for trait_id in sorted(traits):
            trait_def = trait_defs.get(trait_id)
            if trait_def is None or not trait_def.warning:
                continue
            for source in active.trait_sources_by_item[item_id].get(trait_id) or ["unknown"]:
                schedule["warnings"].append(
                    {
                        "item": item_id,
                        "product": active.item_products[item_id],
                        "substance": source,
                        "trait": trait_id,
                        "message": trait_def.description or "Manual review required.",
                        "action": trait_def.action or "",
                    }
                )


def _append_read_model_warnings(
    schedule: dict[str, Any],
    read_model: StackReadModel,
    active_substance_ids: set[str],
) -> None:
    schedule["warnings"].extend(read_model.collect_missing_balance_relations(active_substance_ids))
    schedule["warnings"].extend(read_model.collect_missing_support_relations(active_substance_ids))
    schedule["warnings"].extend(read_model.collect_review_with_relations(active_substance_ids))
