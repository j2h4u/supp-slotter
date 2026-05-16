"""Plan-command schedule.yaml assembly.

Extracted from `planner.engine.plan` to keep the scheduler module focused
on search + orchestration. This module owns the conversion from a solved
assignment dict into the full `schedule` dict that gets written to disk —
benefits/risks/warnings aggregation, pillbox population, explanations,
relation warnings, and humanize-rewrite of the raw warning stream.
"""

from __future__ import annotations

from typing import Any

from planner.cards.dashboards import build_dashboard_review
from planner.cards.pillboxes import build_empty_schedule_pillboxes
from planner.cards.product import (
    collect_product_substance_refs,
    format_item_product_name,
)
from planner.cards.relations_surreal import (
    SurrealSession,
    active_fact_index,
    collect_antagonizing_relations,
    collect_missing_balance_relations,
    collect_missing_support_relations,
)
from planner.cards.schedule import build_placement_notes, build_schedule_summary
from planner.cards.substance import format_substance_name
from planner.cards.traits import readable_traits
from planner.cards.warnings import (
    collect_active_safety_concerns,
    humanize_warning,
    is_generic_manual_review_warning,
)
from planner.contracts import Relation, Slot
from planner.engine._plan_inputs import ActiveIndex
from planner.engine._scheduling import build_substance_slot_names, explain_slot_choice


def build_schedule_output(
    assignment: dict[str, str],
    best_metrics: tuple[float, int, int, float],
    slots: dict[str, Slot],
    active: ActiveIndex,
    item_id_sequence: list[str],
    products: dict[str, Any],
    substances: dict[str, Any],
    relations: list[Relation],
    trait_defs: dict[str, Any],
    prefer_pairs: set[frozenset[str]],
    substance_to_active_items: dict[str, list[str]],
    stack_entries: dict[str, Any],
    dashboard_files: list[Any],
    pillboxes: Any,
    warnings_prefix: list[dict[str, Any]],
    db: SurrealSession,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the complete schedule dict from a solved assignment.

    Returns the schedule dict ready to be serialised (excluding the write step).
    """
    schedule: dict[str, Any] = {
        "summary": {},
        "placement_notes": [],
        "pillboxes": build_empty_schedule_pillboxes(pillboxes),
        "benefits": [],
        "risks": [],
        "warnings": [],
        "kept_together": [
            {
                "pair": sorted(
                    [
                        format_item_product_name(item_id, active.item_products, products)
                        for item_id in sorted(p)
                    ],
                    key=str.casefold,
                ),
                "together": (
                    assignment[sorted(p)[0]] == assignment[sorted(p)[1]]
                ),
                "slot": assignment[sorted(p)[0]]
                if assignment[sorted(p)[0]] == assignment[sorted(p)[1]]
                else None,
            }
            for p in (sorted(prefer_pairs, key=lambda x: sorted(x)))
        ],
        "explanations": {},
    }

    for sid in item_id_sequence:
        slot_name = assignment[sid]
        pillbox_name = slots[slot_name].pillbox
        schedule["pillboxes"][pillbox_name]["slots"][slot_name]["products"].append(
            format_item_product_name(sid, active.item_products, products)
        )
    for pillbox in schedule["pillboxes"].values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"] = sorted(slot_entry["products"], key=str.casefold)

    for slot_name, slot in slots.items():
        pillbox_name = slot.pillbox
        slot_entry = schedule["pillboxes"][pillbox_name]["slots"][slot_name]
        slot_item_ids = [
            item_id for item_id in item_id_sequence if assignment[item_id] == slot_name
        ]
        slot_entry["substances"] = build_substance_slot_names(
            assigned_item_ids=slot_item_ids,
            item_products=active.item_products,
            products=products,
            substances=substances,
        )

    active_substance_ids = set(substance_to_active_items)
    inactive_product_ids = {
        entry["product"]
        for entry in stack_entries.values()
        if entry.get("stack") == "inactive" and isinstance(entry.get("product"), str)
    }
    inactive_substance_ids = collect_product_substance_refs(products, inactive_product_ids)
    cluster_review = build_dashboard_review(
        dashboard_files=dashboard_files,
        active_substances=active_substance_ids,
        inactive_substances=inactive_substance_ids,
        substances=substances,
    )
    schedule["benefits"] = cluster_review["benefits"]
    schedule["risks"] = cluster_review["risks"]
    schedule["warnings"].extend(cluster_review["warnings"])
    schedule["active_fact_index"] = active_fact_index(
        db,
        item_id_sequence=item_id_sequence,
        item_products=active.item_products,
    )

    for sid in item_id_sequence:
        slot_name = assignment[sid]
        slot = slots[slot_name]
        product_name = format_item_product_name(sid, active.item_products, products)
        components_list: list[str] = []
        for substance_id in active.active_components[sid]:
            substance_dc = substances.get(substance_id)
            if substance_dc is not None:
                components_list.append(format_substance_name(substance_dc))
            else:
                components_list.append(substance_id)
        schedule["explanations"][product_name] = {
            "components": components_list,
            "pillbox": slot.pillbox,
            "slot": slot_name,
            "why_here": explain_slot_choice(active.item_traits[sid], slot, trait_defs),
            "review_tags": readable_traits(active.item_traits[sid], trait_defs),
        }

    for sid, internal_conflicts in active.intra_product_conflicts_by_item.items():
        for conflict in internal_conflicts:
            schedule["warnings"].append(
                {
                    "type": "intra_product_trait_conflict",
                    "item": sid,
                    "product": active.item_products[sid],
                    "trait": conflict["trait"],
                    "conflicts_with": conflict["conflicts_with"],
                    "substances": conflict["substances"],
                    "conflicting_substances": conflict["conflicting_substances"],
                    "message": (
                        "Component traits conflict inside one physical product; "
                        "scheduling keeps the product together and emits this warning"
                    ),
                }
            )
    for _sid, internal_conflicts in active.intra_product_relation_conflicts_by_item.items():
        for conflict in internal_conflicts:
            schedule["warnings"].append(conflict)

    schedule["warnings"].extend(
        collect_active_safety_concerns(
            active_order=item_id_sequence,
            active_components=active.active_components,
            item_products=active.item_products,
            products=products,
            substances=substances,
        )
    )
    schedule["warnings"].extend(warnings_prefix)

    for sid, traits in active.item_traits.items():
        for trait_id in sorted(traits):
            trait_def = trait_defs.get(trait_id)
            if trait_def is not None and trait_def.warning:
                for source in active.trait_sources_by_item[sid].get(trait_id) or ["unknown"]:
                    schedule["warnings"].append(
                        {
                            "item": sid,
                            "product": active.item_products[sid],
                            "substance": source,
                            "trait": trait_id,
                            "message": trait_def.description or "Manual review required.",
                            "action": trait_def.action or "",
                        }
                    )

    for warning in collect_missing_balance_relations(db, active_substance_ids):
        schedule["warnings"].append(warning)
    for warning in collect_missing_support_relations(db, active_substance_ids):
        schedule["warnings"].append(warning)
    for warning in collect_antagonizing_relations(db, active_substance_ids):
        schedule["warnings"].append(warning)

    raw_warnings = list(schedule["warnings"])
    schedule["warnings"] = [
        humanize_warning(warning, products=products, substances=substances)
        for warning in schedule["warnings"]
        if not is_generic_manual_review_warning(warning)
    ]
    schedule["placement_notes"] = build_placement_notes(schedule)
    schedule["summary"] = build_schedule_summary(schedule)

    return schedule, raw_warnings
