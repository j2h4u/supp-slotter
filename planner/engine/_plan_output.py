"""Plan-command schedule.yaml assembly.

Extracted from `planner.engine.plan` to keep the scheduler module focused
on search + orchestration. This module owns the conversion from a solved
assignment dict into the full `schedule` dict that gets written to disk —
benefits/risks/warnings aggregation, pillbox population, explanations,
relation warnings, and humanize-rewrite of the raw warning stream.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, cast

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
from planner.contracts import Pillbox, Product, Slot, StackEntry, Substance, TraitDef
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import build_substance_slot_names, explain_slot_choice
from planner.query_model import StackReadModel
from planner.query_model.relation_warnings import RelationWarningRow
from planner.schedule_types import (
    DashboardReviewEntryWithMembers,
    DashboardReviewResult,
    ScheduleData,
    ScheduleExplanation,
    ScheduleKeptTogether,
    SchedulePillbox,
    SchedulePlacementNote,
    ScheduleSummary,
    ScheduleWarning,
)


class ScheduleOutputInput(NamedTuple):
    assignment: dict[str, str]
    slots: dict[str, Slot]
    active: ActiveIndex
    item_id_sequence: list[str]
    products: dict[str, Product]
    substances: dict[str, Substance]
    trait_defs: dict[str, TraitDef]
    prefer_pairs: set[frozenset[str]]
    stack_entries: dict[str, StackEntry]
    dashboard_files: list[Path]
    pillboxes: dict[str, Pillbox]
    warnings_prefix: list[ScheduleWarning]
    read_model: StackReadModel


class _SchedulePillboxContext(NamedTuple):
    schedule: ScheduleData
    assignment: dict[str, str]
    slots: dict[str, Slot]
    active: ActiveIndex
    item_id_sequence: list[str]
    products: dict[str, Product]
    substances: dict[str, Substance]


def build_schedule_output(
    output_input: ScheduleOutputInput,
) -> tuple[ScheduleData, list[ScheduleWarning]]:
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
    pillbox_context = _SchedulePillboxContext(
        schedule=schedule,
        assignment=assignment,
        slots=slots,
        active=active,
        item_id_sequence=item_id_sequence,
        products=products,
        substances=substances,
    )
    _populate_pillbox_products(pillbox_context)
    _populate_pillbox_substances(pillbox_context)

    active_substance_ids = {
        component_id for component_ids in active.active_components.values() for component_id in component_ids
    }
    cluster_review = cast(
        DashboardReviewResult,
        build_dashboard_review(
            dashboard_files=output_input.dashboard_files,
            products=products,
            stack_entries=output_input.stack_entries,
            substances=substances,
        ),
    )
    schedule["benefits"] = cluster_review["benefits"]
    schedule["risks"] = cluster_review["risks"]
    schedule["warnings"].extend(cluster_review["warnings"])
    schedule["active_fact_index"] = cast(
        list[dict[str, object]],
        read_model.active_fact_index(
            item_id_sequence=item_id_sequence,
            item_products=active.item_products,
        ),
    )

    _populate_explanations(schedule, output_input)
    _append_intra_product_relation_conflicts(schedule, active)

    schedule["warnings"].extend(
        cast(
            list[ScheduleWarning],
            collect_active_safety_concerns(
                active_order=item_id_sequence,
                active_components=active.active_components,
                item_products=active.item_products,
                products=products,
                substances=substances,
            ),
        )
    )
    schedule["warnings"].extend(output_input.warnings_prefix)
    _append_trait_warnings(schedule, active, trait_defs)
    _append_read_model_warnings(schedule, read_model, active_substance_ids)

    raw_warnings = list(schedule["warnings"])
    schedule["warnings"] = [
        cast(
            ScheduleWarning,
            humanize_warning(cast(dict[str, object], warning), products=products, substances=substances),
        )
        for warning in schedule["warnings"]
        if not is_generic_manual_review_warning(cast(dict[str, object], warning))
    ]
    schedule["placement_notes"] = cast(
        list[SchedulePlacementNote],
        build_placement_notes(cast(dict[str, object], schedule)),
    )
    schedule["summary"] = cast(ScheduleSummary, build_schedule_summary(cast(dict[str, object], schedule)))

    return schedule, raw_warnings


def _initial_schedule(
    pillboxes: dict[str, Pillbox],
    assignment: dict[str, str],
    active: ActiveIndex,
    products: dict[str, Product],
    prefer_pairs: set[frozenset[str]],
) -> ScheduleData:
    return {
        "summary": cast(ScheduleSummary, {"take": {}}),
        "placement_notes": cast(list[SchedulePlacementNote], []),
        "pillboxes": cast(dict[str, SchedulePillbox], build_empty_schedule_pillboxes(pillboxes)),
        "benefits": cast(list[DashboardReviewEntryWithMembers], []),
        "risks": cast(list[DashboardReviewEntryWithMembers], []),
        "warnings": cast(list[ScheduleWarning], []),
        "kept_together": cast(
            list[ScheduleKeptTogether],
            [
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
        ),
        "explanations": cast(dict[str, ScheduleExplanation], {}),
        "active_fact_index": cast(list[dict[str, object]], []),
    }


def _populate_pillbox_products(context: _SchedulePillboxContext) -> None:
    for item_id in context.item_id_sequence:
        slot_name = context.assignment[item_id]
        pillbox_name = context.slots[slot_name].pillbox
        context.schedule["pillboxes"][pillbox_name]["slots"][slot_name]["products"].append(
            format_item_product_name(item_id, context.active.item_products, context.products)
        )
    for pillbox in context.schedule["pillboxes"].values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"] = sorted(slot_entry["products"], key=str.casefold)


def _populate_pillbox_substances(context: _SchedulePillboxContext) -> None:
    for slot_name, slot in context.slots.items():
        pillbox_name = slot.pillbox
        slot_entry = context.schedule["pillboxes"][pillbox_name]["slots"][slot_name]
        slot_item_ids = [item_id for item_id in context.item_id_sequence if context.assignment[item_id] == slot_name]
        slot_entry["substances"] = build_substance_slot_names(
            assigned_item_ids=slot_item_ids,
            item_products=context.active.item_products,
            products=context.products,
            substances=context.substances,
        )


def _populate_explanations(
    schedule: ScheduleData,
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


def _component_names(component_ids: list[str], substances: dict[str, Substance]) -> list[str]:
    names: list[str] = []
    for substance_id in component_ids:
        substance_dc = substances.get(substance_id)
        names.append(format_substance_name(substance_dc) if substance_dc is not None else substance_id)
    return names


def _append_intra_product_relation_conflicts(schedule: ScheduleData, active: ActiveIndex) -> None:
    for relation_conflicts in active.intra_product_relation_conflicts_by_item.values():
        for conflict in relation_conflicts:
            warning: ScheduleWarning = {
                "type": conflict["type"],
                "item": conflict["item"],
                "product": conflict["product"],
                "relation": conflict["relation"],
                "source_substance": conflict["source_substance"],
                "target_substance": conflict["target_substance"],
                "message": conflict["message"],
                "action": conflict["action"],
            }
            schedule["warnings"].append(warning)


def _append_trait_warnings(
    schedule: ScheduleData,
    active: ActiveIndex,
    trait_defs: dict[str, TraitDef],
) -> None:
    for item_id, traits in active.item_traits.items():
        for trait_id in sorted(traits):
            trait_def = trait_defs.get(trait_id)
            if trait_def is None or not trait_def.warning:
                continue
            for source in active.trait_sources_by_item[item_id].get(trait_id) or ["unknown"]:
                schedule["warnings"].append({
                    "item": item_id,
                    "product": active.item_products[item_id],
                    "substance": source,
                    "trait": trait_id,
                    "message": trait_def.description or "Manual review required.",
                    "action": trait_def.action or "",
                })


def _append_read_model_warnings(
    schedule: ScheduleData,
    read_model: StackReadModel,
    active_substance_ids: set[str],
) -> None:
    for row in read_model.collect_missing_balance_relations(active_substance_ids):
        schedule["warnings"].append(_relation_warning_to_schedule_warning(row))
    for row in read_model.collect_missing_support_relations(active_substance_ids):
        schedule["warnings"].append(_relation_warning_to_schedule_warning(row))
    for row in read_model.collect_review_with_relations(active_substance_ids):
        schedule["warnings"].append(_relation_warning_to_schedule_warning(row))


def _relation_warning_to_schedule_warning(row: RelationWarningRow) -> ScheduleWarning:
    warning: ScheduleWarning = {
        "type": row["type"],
        "source_substance": row["source_substance"],
        "source_name": row["source_name"],
        "target_substance": row["target_substance"],
        "target_name": row["target_name"],
        "reason": row["reason"],
        "action": row["action"],
    }
    if "severity" in row:
        warning["severity"] = row["severity"]
    return warning
