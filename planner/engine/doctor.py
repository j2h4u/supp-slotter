"""`doctor` command: orphan/cleanup candidate report."""

from __future__ import annotations

from planner.cards import (
    collect_dashboard_substance_refs,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    collect_product_substance_refs,
    collect_similar_substances,
    flatten_trait_defs,
    format_relation_warning,
    global_relation_refs,
    load_global_relations,
    load_product,
    load_substance,
    normalize_stack_entries,
)
from planner.io import (
    DASHBOARDS_DIR,
    DATA_DIR,
    PRODUCTS_DIR,
    STACKS_PATH,
    SUBSTANCES_DIR,
    load_yaml,
    validate_schemas,
)
from planner.maintenance import run_auto_maintenance


def collect_orphans() -> dict[str, list[str]]:
    substance_files = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    product_files = sorted(PRODUCTS_DIR.glob("*.yaml"))
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []

    substances: dict[str, dict] = {}
    for sf in substance_files:
        substance, err = load_substance(sf)
        if err:
            continue
        substance_id = substance.get("id")
        if isinstance(substance_id, str):
            substances[substance_id] = substance

    products: dict[str, dict] = {}
    product_substance_refs: set[str] = set()
    for pf in product_files:
        product, err = load_product(pf)
        if err:
            continue
        product_id = product.get("id")
        if isinstance(product_id, str):
            products[product_id] = product
        for component in product.get("components") or []:
            if not isinstance(component, dict):
                continue
            substance_id = component.get("substance")
            if isinstance(substance_id, str):
                product_substance_refs.add(substance_id)

    prefer_with_refs: set[str] = set()
    relation_refs: set[str] = set()
    trait_refs: set[str] = set()
    for substance_id, substance in substances.items():
        if substance.get("prefer_with"):
            prefer_with_refs.add(substance_id)
        for target_id in substance.get("prefer_with") or []:
            if isinstance(target_id, str):
                prefer_with_refs.add(target_id)
        for trait_id in substance.get("traits") or []:
            if isinstance(trait_id, str):
                trait_refs.add(trait_id)
    relation_refs.update(global_relation_refs(substances, load_global_relations()))

    traits_data = load_yaml(DATA_DIR / "traits.yaml")
    traits = flatten_trait_defs(traits_data) if isinstance(traits_data, dict) else {}
    for trait in traits.values():
        if not isinstance(trait, dict):
            continue
        for target_id in trait.get("separate_from") or []:
            if isinstance(target_id, str):
                trait_refs.add(target_id)

    stacks_data = load_yaml(STACKS_PATH)
    stack_entries = (
        normalize_stack_entries(stacks_data)
        if isinstance(stacks_data, dict)
        else {}
    )
    stack_products = {
        entry["product"]
        for entry in stack_entries.values()
        if isinstance(entry, dict) and isinstance(entry.get("product"), str)
    }
    active_stack_products = {
        entry["product"]
        for entry in stack_entries.values()
        if (
            isinstance(entry, dict)
            and entry.get("stack") != "inactive"
            and isinstance(entry.get("product"), str)
        )
    }
    active_substances = collect_product_substance_refs(
        products, active_stack_products
    )
    stack_groups = stacks_data if isinstance(stacks_data, dict) else {}
    if not isinstance(stack_groups, dict):
        stack_groups = {}

    slots_data = load_yaml(DATA_DIR / "pillboxes.yaml")
    pillbox_stacks = set(slots_data) if isinstance(slots_data, dict) else set()

    substance_refs = (
        product_substance_refs
        | collect_dashboard_substance_refs(dashboard_files)
        | prefer_with_refs
        | relation_refs
    )
    unused_substances = sorted(set(substances) - substance_refs)
    products_without_stack = sorted(set(products) - stack_products)
    unused_traits = sorted(set(traits) - trait_refs)
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

