"""`check` command: full-repo YAML validation with auto-maintenance pass."""

from __future__ import annotations

from planner.cards.dashboards import check_dashboards
from planner.cards.pillboxes import check_pillbox_slot_ids, load_pillboxes
from planner.cards.product import check_product_formulas
from planner.cards.relations import check_global_relations
from planner.cards.stacks import validate_stacks
from planner.cards.substance import check_substances, load_substance_registry
from planner.cards.traits import check_traits, load_traits
from planner.contracts import CardLoadError
from planner.io import (
    DASHBOARDS_DIR,
    DATA_DIR,
    PRODUCTS_DIR,
    RELATIONS_PATH,
    STACKS_PATH,
    SUBSTANCES_DIR,
    load_yaml,
    report,
    schema_errors,
)
from planner.maintenance import run_auto_maintenance


def cmd_check() -> int:
    maintenance_result = run_auto_maintenance(quiet=True)
    if maintenance_result != 0:
        return maintenance_result

    errors: list[str] = []
    info: list[str] = []

    slots_path = DATA_DIR / "pillboxes.yaml"
    traits_path = DATA_DIR / "traits.yaml"

    for required in (slots_path, traits_path, RELATIONS_PATH):
        if not required.exists():
            return report([f"missing: {required}"], [])

    slots_data = load_yaml(slots_path)
    traits_data = load_yaml(traits_path)

    if not isinstance(slots_data, dict):
        return report([f"{slots_path}: top-level must be a mapping"], [])
    if not isinstance(traits_data, dict):
        return report([f"{traits_path}: top-level must be a mapping"], [])

    errors.extend(schema_errors(slots_data, "pillboxes", slots_path))
    errors.extend(schema_errors(traits_data, "traits", traits_path))

    if errors:
        return report(errors, info)

    try:
        pillboxes = load_pillboxes(slots_path)
    except CardLoadError as e:
        return report([e.message], info)
    try:
        trait_defs = load_traits(traits_path)
    except CardLoadError as e:
        return report([e.message], info)

    errors.extend(check_pillbox_slot_ids(pillboxes, slots_path))
    errors.extend(check_traits(trait_defs, traits_path))

    trait_ids = set(trait_defs)

    all_substance_files = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    s_errors, s_info, substance_ids = check_substances(all_substance_files, trait_ids)
    errors.extend(s_errors)
    info.extend(s_info)
    substances = load_substance_registry()
    relations_data = load_yaml(RELATIONS_PATH)
    errors.extend(check_global_relations(relations_data, substances))

    all_product_files = sorted(PRODUCTS_DIR.glob("*.yaml"))
    p_errors, p_info, product_ids = check_product_formulas(
        all_product_files, substance_ids
    )
    errors.extend(p_errors)
    info.extend(p_info)

    errors.extend(validate_stacks(STACKS_PATH, product_ids, trait_ids))
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []
    errors.extend(check_dashboards(dashboard_files, substance_ids, substances))

    return report(errors, info)
