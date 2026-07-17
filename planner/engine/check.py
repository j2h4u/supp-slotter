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
from planner.check_report import report
from planner.contracts import CardLoadError
from planner.engine.results import CheckResult
from planner.maintenance import run_auto_maintenance
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.policies import check_scheduling_policies, load_scheduling_policies
from planner.paths import ROOT, Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import load_yaml


def cmd_check(data_root: Path | None = None) -> CheckResult:
    """Run auto-maintenance first so check operates on normalised filenames and ids; returns exit_code 0 only when all card cross-references are clean."""
    paths = Paths.from_root(data_root) if data_root is not None else Paths.default()
    try:
        bundle = load_ontology(ROOT / "ontology")
    except OntologyInfrastructureError as e:
        message = f"check: ontology: {e}"
        report([message], [])
        return CheckResult(exit_code=1, errors=[message], info=[])
    return _cmd_check_inner(paths, bundle)


def _cmd_check_inner(paths: Paths, bundle: OntologyBundle) -> CheckResult:
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

    schema_preflight = _schema_preflight_errors(paths, info, bundle)
    if schema_preflight is not None:
        return schema_preflight

    domain_result = _load_domain_validators(paths, info, bundle)
    if domain_result.exit_code != 0:
        return domain_result

    errors.extend(domain_result.errors)
    card_validation_result = _extend_card_validation_errors(paths, errors, info, bundle)
    if card_validation_result is not None:
        return card_validation_result

    exit_code = report(errors, info)
    return CheckResult(exit_code=exit_code, errors=errors, info=info)


def _missing_required_file_error(paths: Paths) -> str | None:
    slots_path = paths.data / "pillboxes.yaml"
    for required in (slots_path, paths.relations_file):
        if not required.exists():
            return f"missing: {required}"
    return None


def _schema_preflight_errors(
    paths: Paths, info: list[str], bundle: OntologyBundle
) -> CheckResult | None:
    slots_path = paths.data / "pillboxes.yaml"
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

    errors.extend(schema_errors(slots_data, "pillboxes", slots_path, bundle))
    if errors:
        report(errors, info)
        return CheckResult(exit_code=1, errors=errors, info=info)
    return None


def _load_domain_validators(paths: Paths, info: list[str], bundle: OntologyBundle) -> CheckResult:
    errors: list[str] = []
    slots_path = paths.data / "pillboxes.yaml"
    try:
        pillboxes = load_pillboxes(slots_path)
    except CardLoadError as e:
        report([e.message], info)
        return CheckResult(exit_code=1, errors=[e.message], info=info)
    try:
        policies = load_scheduling_policies(bundle)
    except CardLoadError as e:
        report([e.message], info)
        return CheckResult(exit_code=1, errors=[e.message], info=info)

    errors.extend(check_pillbox_slot_ids(pillboxes, slots_path))
    errors.extend(check_scheduling_policies(policies, ROOT / "ontology"))
    return CheckResult(exit_code=0, errors=errors, info=info)


def _extend_card_validation_errors(
    paths: Paths,
    errors: list[str],
    info: list[str],
    bundle: OntologyBundle,
) -> CheckResult | None:
    policies = load_scheduling_policies(bundle)
    trait_ids = set(policies)
    all_substance_files = sorted(paths.substances.glob("*.yaml"))
    s_errors, s_info, substance_ids = check_substances(
        all_substance_files, trait_ids, paths, bundle
    )
    errors.extend(s_errors)
    info.extend(s_info)
    substances = load_substance_registry(paths, bundle)
    try:
        relations_data = load_yaml(paths.relations_file)
    except CardLoadError as e:
        report([e.message], info)
        return CheckResult(exit_code=1, errors=[e.message], info=info)
    errors.extend(check_global_relations(relations_data, substances, paths, bundle))

    all_product_files = sorted(paths.products.glob("*.yaml"))
    p_errors, p_info, product_ids = check_product_formulas(
        all_product_files, substance_ids, bundle
    )
    errors.extend(p_errors)
    info.extend(p_info)

    stacks_errors, stacks_info = validate_stacks(paths, product_ids, bundle)
    errors.extend(stacks_errors)
    info.extend(stacks_info)
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    errors.extend(check_dashboards(dashboard_files, trait_ids, paths, bundle))
    return None
