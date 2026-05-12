"""`check` command: full-repo YAML validation with auto-maintenance pass."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from planner.cards.dashboards import check_dashboards
from planner.cards.pillboxes import check_pillbox_slot_ids, load_pillboxes
from planner.cards.product import check_product_formulas
from planner.cards.relations import check_global_relations
from planner.cards.stacks import validate_stacks
from planner.cards.substance import check_substances, load_substance_registry
from planner.cards.traits import check_traits, load_traits
from planner.contracts import CardLoadError
from planner.engine._root_patch import maybe_patch_root
from planner.engine.results import CheckResult
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


def cmd_check(data_root: Path | None = None) -> CheckResult:
    """Run auto-maintenance first so check operates on normalised filenames and ids; returns exit_code 0 only when all card cross-references are clean."""
    with maybe_patch_root(data_root):
        return _cmd_check_inner()


def _cmd_check_inner() -> CheckResult:
    errors: list[str] = []
    info: list[str] = []
    maintenance_result = run_auto_maintenance(suppress_output=True, collect_errors=errors)
    if maintenance_result != 0:
        print("check: skipped (auto-maintenance failed; see errors above)", file=sys.stderr)
        return CheckResult(exit_code=maintenance_result, errors=errors, info=info)

    slots_path = DATA_DIR / "pillboxes.yaml"
    traits_path = DATA_DIR / "traits.yaml"

    for required in (slots_path, traits_path, RELATIONS_PATH):
        if not required.exists():
            msg = f"missing: {required}"
            report([msg], [])
            return CheckResult(exit_code=1, errors=[msg], info=[])

    slots_data = load_yaml(slots_path)
    traits_data = load_yaml(traits_path)

    if not isinstance(slots_data, dict):
        msg = f"{slots_path}: top-level must be a mapping"
        report([msg], [])
        return CheckResult(exit_code=1, errors=[msg], info=[])
    if not isinstance(traits_data, dict):
        msg = f"{traits_path}: top-level must be a mapping"
        report([msg], [])
        return CheckResult(exit_code=1, errors=[msg], info=[])

    slots_dict = cast(dict[str, Any], slots_data)
    traits_dict = cast(dict[str, Any], traits_data)
    errors.extend(schema_errors(slots_dict, "pillboxes", slots_path))
    errors.extend(schema_errors(traits_dict, "traits", traits_path))

    if errors:
        report(errors, info)
        return CheckResult(exit_code=1, errors=errors, info=info)

    try:
        pillboxes = load_pillboxes(slots_path)
    except CardLoadError as e:
        report([e.message], info)
        return CheckResult(exit_code=1, errors=[e.message], info=info)
    try:
        trait_defs = load_traits(traits_path)
    except CardLoadError as e:
        report([e.message], info)
        return CheckResult(exit_code=1, errors=[e.message], info=info)

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

    stacks_errors, stacks_info = validate_stacks(STACKS_PATH, product_ids)
    errors.extend(stacks_errors)
    info.extend(stacks_info)
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []
    errors.extend(check_dashboards(dashboard_files, substance_ids, substances, trait_ids))

    exit_code = report(errors, info)
    return CheckResult(exit_code=exit_code, errors=errors, info=info)
