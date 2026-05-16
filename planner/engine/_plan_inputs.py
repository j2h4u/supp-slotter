"""Plan-command input loaders and active-stack indexing.

Extracted from `planner.engine.plan` to keep the scheduler module focused
on search + orchestration. This module owns:

- `PlanInputs` / `ActiveIndex` NamedTuples
- `load_plan_inputs` — read pillboxes/traits/stacks/substances/products/relations
- `build_active_index` — derive per-item trait/component/conflict indexes
- `resolve_prefer_pairs` — collapse substance-level `prefer_with` into item-pairs
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, NamedTuple, cast

from planner.cards.pillboxes import flatten_pillbox_slots, load_pillboxes
from planner.cards.product import (
    load_product_registry,
    product_component_substances,
)
from planner.cards.relations import load_global_relations
from planner.cards.relations_surreal import (
    SurrealSession,
    collect_intra_product_relation_conflicts,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import load_substance_registry
from planner.cards.traits import load_traits
from planner.contracts import (
    CardLoadError,
    Pillbox,
    Product,
    Relation,
    Slot,
    Substance,
    TraitDef,
)
from planner.engine._scheduling import effective_stack_item_traits
from planner.io import Paths, load_yaml


class PlanInputs(NamedTuple):
    slots: dict[str, Slot]
    trait_defs: dict[str, TraitDef]
    substances: dict[str, Substance]
    products: dict[str, Product]
    global_relations: list[Relation]
    dashboard_files: list[Path]
    stack_entries: dict[str, Any]
    pillboxes: dict[str, Pillbox]


class ActiveIndex(NamedTuple):
    item_traits: dict[str, set[str]]
    secondary_traits_by_item: dict[str, set[str]]
    item_products: dict[str, str]
    active_components: dict[str, list[str]]
    trait_sources_by_item: dict[str, dict[str, list[str]]]
    intra_product_conflicts_by_item: dict[str, list[dict[str, Any]]]
    intra_product_relation_conflicts_by_item: dict[str, list[dict[str, Any]]]
    item_stacks: dict[str, str]


def load_plan_inputs(
    paths: Paths,
) -> PlanInputs | None:
    """Load all static inputs needed before the active-index build.

    Returns a PlanInputs or None on failure.
    """
    try:
        pillboxes = load_pillboxes(paths.data / "pillboxes.yaml")
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    try:
        trait_defs = load_traits(paths.data / "traits.yaml")
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    stacks_data = load_yaml(paths.stacks_file)

    if not isinstance(stacks_data, dict):
        print("plan: stacks.yaml: top-level must be a mapping", file=sys.stderr)
        return None

    stacks_dict = cast(dict[str, Any], stacks_data)
    slots: dict[str, Slot] = dict(
        sorted(
            flatten_pillbox_slots(pillboxes).items(),
            key=lambda kv: (kv[1].pillbox, kv[1].order),
        )
    )

    substances = load_substance_registry(paths)
    products = load_product_registry(paths)
    global_relations = load_global_relations(paths)
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    stack_entries = normalize_stack_entries(stacks_dict)

    return PlanInputs(
        slots=slots,
        trait_defs=trait_defs,
        substances=substances,
        products=products,
        global_relations=global_relations,
        dashboard_files=dashboard_files,
        stack_entries=stack_entries,
        pillboxes=pillboxes,
    )


def build_active_index(
    stack_entries: dict[str, Any],
    products: dict[str, Any],
    substances: dict[str, Any],
    trait_defs: dict[str, Any],
    global_relations: list[Relation],
    slots: dict[str, Slot],
    errors: list[str],
    db: SurrealSession,
) -> ActiveIndex | None:
    """Build per-item trait/conflict/stack indexes from the active stack entries.

    Returns an ActiveIndex or None if any early-exit condition is hit.
    Appends human-readable error messages to *errors* before returning None.
    """
    item_traits: dict[str, set[str]] = {}
    secondary_traits_by_item: dict[str, set[str]] = {}
    item_products: dict[str, str] = {}
    active_components: dict[str, list[str]] = {}
    trait_sources_by_item: dict[str, dict[str, list[str]]] = {}
    intra_product_conflicts_by_item: dict[str, list[dict[str, Any]]] = {}
    intra_product_relation_conflicts_by_item: dict[str, list[dict[str, Any]]] = {}
    item_stacks: dict[str, str] = {}

    for item_id, entry in stack_entries.items():
        stack = entry.get("stack")
        if stack == "inactive":
            continue
        product_id = entry.get("product")
        product = products.get(product_id) if isinstance(product_id, str) else None
        if product is None or not isinstance(product_id, str):
            print(
                f"plan: skipping '{item_id}' — product '{product_id}' missing or invalid",
                file=sys.stderr,
            )
            continue
        effective, _primary_traits, secondary_only_traits, trait_sources, internal_conflicts = (
            effective_stack_item_traits(product, substances, trait_defs)
        )
        item_traits[item_id] = effective
        secondary_traits_by_item[item_id] = secondary_only_traits
        item_products[item_id] = product_id
        active_components[item_id] = product_component_substances(product)
        trait_sources_by_item[item_id] = trait_sources
        intra_product_conflicts_by_item[item_id] = internal_conflicts
        intra_product_relation_conflicts_by_item[item_id] = (
            collect_intra_product_relation_conflicts(
                db,
                item_id=item_id,
                product_id=product_id,
                component_ids=active_components[item_id],
                relation_type="competes",
            )
        )
        item_stacks[item_id] = stack if isinstance(stack, str) else ""

    if not item_traits:
        msg = "plan: no non-inactive stack items."
        print(msg, file=sys.stderr)
        errors.append(msg)
        return None

    workout_stacks = {
        slot.stack
        for slot in slots.values()
        if slot.near.startswith("workout_")
    }
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
        intra_product_conflicts_by_item=intra_product_conflicts_by_item,
        intra_product_relation_conflicts_by_item=intra_product_relation_conflicts_by_item,
        item_stacks=item_stacks,
    )


def resolve_prefer_pairs(
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    substances: dict[str, Any],
) -> tuple[set[frozenset[str]], list[dict[str, Any]], dict[str, list[str]]]:
    """Build prefer_pairs, ambiguous warnings, and substance-to-active-items index.

    Returns (prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items).
    """
    prefer_pairs: set[frozenset[str]] = set()
    ambiguous_prefer_with_warnings: list[dict[str, Any]] = []
    substance_to_active_items: dict[str, list[str]] = {}

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance_to_active_items.setdefault(component_id, []).append(item_id)
    for component_id in substance_to_active_items:
        substance_to_active_items[component_id].sort()

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance = substances.get(component_id)
            if substance is None:
                continue
            for target_substance in substance.prefer_with:
                target_items = substance_to_active_items.get(target_substance, [])
                if len(target_items) == 1:
                    other_item = target_items[0]
                    if other_item != item_id:
                        prefer_pairs.add(frozenset([item_id, other_item]))
                elif len(target_items) > 1:
                    ambiguous_prefer_with_warnings.append(
                        {
                            "type": "ambiguous_prefer_with",
                            "item": item_id,
                            "product": item_products[item_id],
                            "source_substance": component_id,
                            "target_substance": target_substance,
                            "candidate_items": target_items,
                            "message": (
                                "prefer_with target maps to multiple active "
                                "stack items; no bonus awarded"
                            ),
                        }
                    )

    return prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items
