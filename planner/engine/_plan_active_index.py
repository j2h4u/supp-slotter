"""Active-stack indexing for the plan command."""

from __future__ import annotations

import sys
from typing import NamedTuple

from planner.cards.product import product_component_substances
from planner.contracts import Product, Slot, StackEntry, Substance, TraitDef
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import effective_stack_item_traits
from planner.engine._types import ScheduleWarning
from planner.query_model import StackReadModel
from planner.query_model.relation_conflicts import RelationConflictWarningRow


class _ActiveItemIndex(NamedTuple):
    product_id: str
    stack: str
    effective_traits: set[str]
    secondary_traits: set[str]
    active_components: list[str]
    trait_sources: dict[str, list[str]]
    relation_conflicts: list[RelationConflictWarningRow]


def build_active_index(
    stack_entries: dict[str, StackEntry],
    products: dict[str, Product],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    slots: dict[str, Slot],
    errors: list[str],
    read_model: StackReadModel,
) -> ActiveIndex | None:
    """Build per-item trait/conflict/stack indexes from the active stack entries."""
    item_traits: dict[str, set[str]] = {}
    secondary_traits_by_item: dict[str, set[str]] = {}
    item_products: dict[str, str] = {}
    active_components: dict[str, list[str]] = {}
    trait_sources_by_item: dict[str, dict[str, list[str]]] = {}
    intra_product_relation_conflicts_by_item: dict[str, list[RelationConflictWarningRow]] = {}
    item_stacks: dict[str, str] = {}

    for item_id, entry in stack_entries.items():
        item_index = _active_item_index(item_id, entry, products, substances, trait_defs, read_model)
        if item_index is None:
            continue
        item_traits[item_id] = item_index.effective_traits
        secondary_traits_by_item[item_id] = item_index.secondary_traits
        item_products[item_id] = item_index.product_id
        active_components[item_id] = item_index.active_components
        trait_sources_by_item[item_id] = item_index.trait_sources
        intra_product_relation_conflicts_by_item[item_id] = item_index.relation_conflicts
        item_stacks[item_id] = item_index.stack

    if not item_traits:
        msg = "plan: no non-inactive stack items."
        print(msg, file=sys.stderr)
        errors.append(msg)
        return None

    workout_stacks = {slot.stack for slot in slots.values() if slot.near.startswith("workout_")}
    for item_id, traits in item_traits.items():
        activity_traits = sorted(trait for trait in traits if trait.startswith("activity:"))
        if activity_traits and item_stacks[item_id] not in workout_stacks:
            msg = (
                f"plan: stack item '{item_id}' has {', '.join(activity_traits)} "
                f"but stack '{item_stacks[item_id]}' has no workout pillbox slots."
            )
            print(msg, file=sys.stderr)
            errors.append(msg)
            return None

    return ActiveIndex(
        item_traits=item_traits,
        secondary_traits_by_item=secondary_traits_by_item,
        item_products=item_products,
        active_components=active_components,
        trait_sources_by_item=trait_sources_by_item,
        intra_product_relation_conflicts_by_item=intra_product_relation_conflicts_by_item,
        item_stacks=item_stacks,
    )


def _active_item_index(
    item_id: str,
    entry: StackEntry,
    products: dict[str, Product],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    read_model: StackReadModel,
) -> _ActiveItemIndex | None:
    stack = entry.get("stack")
    if stack == "inactive":
        return None
    product_id = entry.get("product")
    product = products.get(product_id)
    if product is None:
        print(
            f"plan: skipping '{item_id}' - product '{product_id}' missing or invalid",
            file=sys.stderr,
        )
        return None
    effective, _primary_traits, secondary_only_traits, trait_sources = effective_stack_item_traits(
        product, substances, trait_defs
    )
    active_components = product_component_substances(product)
    relation_conflicts = read_model.collect_intra_product_relation_conflicts(
        item_id=item_id,
        product_id=product_id,
        component_ids=active_components,
        relation_type="competes",
    )
    return _ActiveItemIndex(
        product_id=product_id,
        stack=stack,
        effective_traits=effective,
        secondary_traits=secondary_only_traits,
        active_components=active_components,
        trait_sources=trait_sources,
        relation_conflicts=relation_conflicts,
    )


def resolve_prefer_pairs(
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    substances: dict[str, Substance],
) -> tuple[set[frozenset[str]], list[ScheduleWarning], dict[str, list[str]]]:
    """Build prefer pairs, ambiguity warnings, and substance-to-active-items index."""
    prefer_pairs: set[frozenset[str]] = set()
    ambiguous_prefer_with_warnings: list[ScheduleWarning] = []
    substance_to_active_items = _substance_to_active_items(active_components)

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance = substances.get(component_id)
            if substance is None:
                continue
            for target_substance in substance.prefer_with:
                _add_prefer_target(
                    prefer_pairs,
                    ambiguous_prefer_with_warnings,
                    item_id=item_id,
                    item_products=item_products,
                    component_id=component_id,
                    target_substance=target_substance,
                    substance_to_active_items=substance_to_active_items,
                )

    return prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items


def _substance_to_active_items(active_components: dict[str, list[str]]) -> dict[str, list[str]]:
    substance_to_active_items: dict[str, list[str]] = {}
    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance_to_active_items.setdefault(component_id, []).append(item_id)
    for component_id in substance_to_active_items:
        substance_to_active_items[component_id].sort()
    return substance_to_active_items


def _add_prefer_target(
    prefer_pairs: set[frozenset[str]],
    ambiguous_prefer_with_warnings: list[ScheduleWarning],
    *,
    item_id: str,
    item_products: dict[str, str],
    component_id: str,
    target_substance: str,
    substance_to_active_items: dict[str, list[str]],
) -> None:
    target_items = substance_to_active_items.get(target_substance, [])
    if len(target_items) == 1:
        other_item = target_items[0]
        if other_item != item_id:
            prefer_pairs.add(frozenset([item_id, other_item]))
        return
    if len(target_items) > 1:
        ambiguous_prefer_with_warnings.append({
            "type": "ambiguous_prefer_with",
            "item": item_id,
            "product": item_products[item_id],
            "source_substance": component_id,
            "target_substance": target_substance,
            "candidate_items": target_items,
            "message": "prefer_with target maps to multiple active stack items; no bonus awarded",
        })
