"""`check` command: full-repo YAML validation with auto-maintenance pass."""

from __future__ import annotations

import sys
from pathlib import Path

from planner.cards.dashboard_validation import check_dashboards
from planner.cards.pillboxes import check_pillbox_slot_ids, load_pillboxes
from planner.cards.product_validation import check_product_formulas
from planner.cards.relations import check_global_relations
from planner.cards.stacks import validate_stacks
from planner.cards.substance import load_substance_registry
from planner.cards.substance_validation import check_substances
from planner.cards.traits import check_traits, load_traits, trait_source_files
from planner.check_report import report
from planner.contracts import CardLoadError
from planner.engine.results import CheckResult
from planner.maintenance import run_auto_maintenance
from planner.paths import Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import load_yaml


def cmd_check(data_root: Path | None = None) -> CheckResult:
    """Run auto-maintenance first so check operates on normalised filenames and ids; returns exit_code 0 only when all card cross-references are clean."""
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    return _cmd_check_inner(paths)


def _cmd_check_inner(paths: Paths) -> CheckResult:
    errors: list[str] = []
    info: list[str] = []
    maintenance_result = run_auto_maintenance(paths, suppress_output=True, collect_errors=errors)
    if maintenance_result != 0:
        print("check: skipped (auto-maintenance failed; see errors above)", file=sys.stderr)
        return CheckResult(exit_code=maintenance_result, errors=errors, info=info)

    required_error = _missing_required_file_error(paths)
    if required_error is not None:
        report([required_error], [])
        return CheckResult(exit_code=1, errors=[required_error], info=[])

    schema_preflight = _schema_preflight_errors(paths, info)
    if schema_preflight is not None:
        return schema_preflight

    domain_result = _load_domain_validators(paths, info)
    if domain_result.exit_code != 0:
        return domain_result

    errors.extend(domain_result.errors)
    card_validation_result = _extend_card_validation_errors(paths, errors, info)
    if card_validation_result is not None:
        return card_validation_result

    exit_code = report(errors, info)
    return CheckResult(exit_code=exit_code, errors=errors, info=info)


def _missing_required_file_error(paths: Paths) -> str | None:
    slots_path = paths.data / "pillboxes.yaml"
    traits_path = paths.traits

    for required in (slots_path, traits_path, paths.relations_file):
        if not required.exists():
            return f"missing: {required}"
    return None


def _schema_preflight_errors(paths: Paths, info: list[str]) -> CheckResult | None:
    slots_path = paths.data / "pillboxes.yaml"
    traits_path = paths.traits
    errors: list[str] = []
    try:
        slots_data = load_yaml(slots_path)
    except CardLoadError as e:
        report([e.message], info)
        return CheckResult(exit_code=1, errors=[e.message], info=info)

    if not isinstance(slots_data, dict):
        msg = f"{slots_path}: top-level must be a mapping"
        report([msg], [])
        return CheckResult(exit_code=1, errors=[msg], info=[])

    errors.extend(schema_errors(slots_data, "pillboxes", slots_path))
    errors.extend(_trait_schema_errors(traits_path, info))
    if errors:
        report(errors, info)
        return CheckResult(exit_code=1, errors=errors, info=info)
    return None


def _trait_schema_errors(traits_path: Path, info: list[str]) -> list[str]:
    errors: list[str] = []
    try:
        trait_files = trait_source_files(traits_path)
    except CardLoadError as e:
        report([e.message], info)
        return [e.message]
    for trait_file in trait_files:
        try:
            traits_data = load_yaml(trait_file)
        except CardLoadError as e:
            report([e.message], info)
            return [e.message]
        if not isinstance(traits_data, dict):
            msg = f"{trait_file}: top-level must be a mapping"
            report([msg], [])
            return [msg]
        errors.extend(schema_errors(traits_data, "traits", trait_file))
    return errors


def _load_domain_validators(paths: Paths, info: list[str]) -> CheckResult:
    errors: list[str] = []
    slots_path = paths.data / "pillboxes.yaml"
    traits_path = paths.traits
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
    return CheckResult(exit_code=0, errors=errors, info=info)


def _extend_card_validation_errors(
    paths: Paths,
    errors: list[str],
    info: list[str],
) -> CheckResult | None:
    trait_defs = load_traits(paths.traits)
    trait_ids = set(trait_defs)
    all_substance_files = sorted(paths.substances.glob("*.yaml"))
    s_errors, s_info, substance_ids = check_substances(all_substance_files, trait_ids, paths)
    errors.extend(s_errors)
    info.extend(s_info)
    substances = load_substance_registry(paths)
    try:
        relations_data = load_yaml(paths.relations_file)
    except CardLoadError as e:
        report([e.message], info)
        return CheckResult(exit_code=1, errors=[e.message], info=info)
    errors.extend(check_global_relations(relations_data, substances, trait_defs, paths))

    all_product_files = sorted(paths.products.glob("*.yaml"))
    p_errors, p_info, product_ids = check_product_formulas(all_product_files, substance_ids)
    errors.extend(p_errors)
    info.extend(p_info)

    stacks_errors, stacks_info = validate_stacks(paths, product_ids)
    errors.extend(stacks_errors)
    info.extend(stacks_info)
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    errors.extend(check_dashboards(dashboard_files, trait_ids, paths))
    return None
