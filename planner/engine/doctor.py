"""`doctor` command: orphan/cleanup candidate report."""

from __future__ import annotations

from typing import Any, cast

from planner.cards.dashboards import collect_dashboard_substance_refs
from planner.cards.product import (
    collect_product_substance_refs,
    load_product_registry,
)
from planner.cards.relations import (
    collect_missing_balance_relations,
    collect_missing_support_relations,
    format_relation_warning,
    global_relation_refs,
    load_global_relations,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import (
    collect_similar_substances,
    load_substance_registry,
)
from planner.cards.traits import load_traits
from planner.io import (
    DASHBOARDS_DIR,
    DATA_DIR,
    STACKS_PATH,
    load_yaml,
    validate_schemas,
)
from planner.maintenance import run_auto_maintenance


def collect_orphans() -> dict[str, list[str]]:
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []

    substances = load_substance_registry()
    products = load_product_registry()

    product_substance_refs: set[str] = set()
    for product in products.values():
        for component in product.components:
            product_substance_refs.add(component.substance)

    prefer_with_refs: set[str] = set()
    relation_refs: set[str] = set()
    trait_refs: set[str] = set()
    for substance_id, substance in substances.items():
        if substance.prefer_with:
            prefer_with_refs.add(substance_id)
        for target_id in substance.prefer_with:
            prefer_with_refs.add(target_id)
        for trait_id in substance.traits:
            trait_refs.add(trait_id)
    relation_refs.update(global_relation_refs(substances, load_global_relations()))

    trait_defs = load_traits(DATA_DIR / "traits.yaml")
    for trait in trait_defs.values():
        for target_id in trait.separate_from:
            trait_refs.add(target_id)

    stacks_data = load_yaml(STACKS_PATH)
    stack_entries = (
        normalize_stack_entries(cast(dict[str, Any], stacks_data))
        if isinstance(stacks_data, dict)
        else {}
    )
    stack_products = {
        cast(str, entry.get("product"))
        for entry in stack_entries.values()
        if isinstance(entry.get("product"), str)
    }
    active_stack_products = {
        cast(str, entry.get("product"))
        for entry in stack_entries.values()
        if entry.get("stack") != "inactive" and isinstance(entry.get("product"), str)
    }
    active_substances = collect_product_substance_refs(
        products, active_stack_products
    )
    stack_groups = cast(dict[str, Any], stacks_data) if isinstance(stacks_data, dict) else {}

    slots_data = load_yaml(DATA_DIR / "pillboxes.yaml")
    slots_dict = cast(dict[str, Any], slots_data) if isinstance(slots_data, dict) else {}
    pillbox_stacks: set[str] = set(slots_dict.keys()) if slots_dict else set()

    substance_refs = (
        product_substance_refs
        | collect_dashboard_substance_refs(dashboard_files)
        | prefer_with_refs
        | relation_refs
    )
    unused_substances = sorted(set(substances) - substance_refs)
    products_without_stack = sorted(set(products) - stack_products)
    unused_traits = sorted(set(trait_defs) - trait_refs)
    empty_stacks = sorted(
        stack
        for stack, items in stack_groups.items()
        if isinstance(items, list) and not items
    )
    stacks_without_pillboxes = sorted(
        set(stack_groups) - pillbox_stacks - {"inactive"}
    )
    pillboxes_without_stack = sorted(pillbox_stacks - set(stack_groups))

    return {
        "substances.unused": unused_substances,
        "products.without_stack": products_without_stack,
        "traits.unused": unused_traits,
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": collect_similar_substances(substances),
        "relations.balance_missing": [
            format_relation_warning(warning)
            for warning in collect_missing_balance_relations(
                substances, active_substances, load_global_relations()
            )
        ],
        "relations.supports_missing": [
            format_relation_warning(warning)
            for warning in collect_missing_support_relations(
                substances, active_substances, load_global_relations()
            )
        ],
    }


def cmd_doctor() -> int:
    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    maintenance_result = run_auto_maintenance(quiet=True)
    if maintenance_result != 0:
        return maintenance_result

    sections = collect_orphans()

    print("Doctor / cleanup candidates")
    for section, items in sections.items():
        print(f"\n{section} ({len(items)})")
        if not items:
            print("  none")
            continue
        for item in items:
            print(f"  - {item}")
    return 0
