"""`check` command: read-only full-repository YAML validation."""

from __future__ import annotations

from pathlib import Path

from planner.cards.dashboard_validation import check_dashboards
from planner.cards.pillboxes import load_pillboxes
from planner.cards.product import load_product_registry
from planner.cards.product_validation import check_product_formulas
from planner.cards.relations import check_global_relations
from planner.cards.stacks import validate_stacks
from planner.cards.substance import load_substance_registry
from planner.cards.substance_validation import check_substances
from planner.check_report import report
from planner.contracts import CardLoadError
from planner.engine.results import CheckResult
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.canonical_facts import validate_canonical_scheduling
from planner.ontology.errors import OntologyInfrastructureError
from planner.paths import ROOT, Paths
from planner.schema_validation import schema_errors
from planner.yaml_io import load_yaml


def cmd_check(data_root: Path | None = None) -> CheckResult:
    """Validate canonical repository inputs without modifying them."""
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

    required_error = _missing_required_file_error(paths)
    if required_error is not None:
        return _check_failure([required_error], info)

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


def _schema_preflight_errors(paths: Paths, info: list[str], bundle: OntologyBundle) -> CheckResult | None:
    slots_path = paths.data / "pillboxes.yaml"
    try:
        slots_data = load_yaml(slots_path)
    except CardLoadError as e:
        return _check_failure([e.message], info)

    if not isinstance(slots_data, dict):
        msg = f"{slots_path}: top-level must be a mapping"
        return _check_failure([msg], info)

    try:
        stacks_data = load_yaml(paths.stacks_file)
    except CardLoadError as e:
        return _check_failure([e.message], info)
    references = (
        {"Stack": {key for key in stacks_data if isinstance(key, str)}} if isinstance(stacks_data, dict) else {}
    )
    errors = schema_errors(slots_data, "pillboxes", slots_path, bundle, reference_values=references)
    if errors:
        return _check_failure(errors, info)
    return None


def _load_domain_validators(paths: Paths, info: list[str], bundle: OntologyBundle) -> CheckResult:
    errors: list[str] = []
    try:
        load_pillboxes(paths.data / "pillboxes.yaml", bundle)
    except CardLoadError as e:
        return _check_failure([e.message], info)
    return CheckResult(exit_code=0, errors=errors, info=info)


def _extend_card_validation_errors(  # noqa: PLR0911, PLR0914
    paths: Paths,
    errors: list[str],
    info: list[str],
    bundle: OntologyBundle,
) -> CheckResult | None:
    all_substance_files = sorted(paths.substances.glob("*.yaml"))
    s_errors, s_info, substance_ids = check_substances(all_substance_files, bundle)
    errors.extend(s_errors)
    info.extend(s_info)
    if s_errors:
        return _check_failure(errors, info)
    try:
        substances = load_substance_registry(paths, bundle)
    except CardLoadError as e:
        errors.append(e.message)
        return _check_failure(errors, info)
    try:
        relations_data = load_yaml(paths.relations_file)
    except CardLoadError as e:
        errors.append(e.message)
        return _check_failure(errors, info)
    relation_errors = check_global_relations(relations_data, substances, paths, bundle)
    errors.extend(relation_errors)
    if relation_errors:
        return _check_failure(errors, info)

    all_product_files = sorted(paths.products.glob("*.yaml"))
    p_errors, p_info, product_ids = check_product_formulas(all_product_files, substance_ids, bundle)
    errors.extend(p_errors)
    info.extend(p_info)
    if p_errors:
        return _check_failure(errors, info)
    try:
        products = load_product_registry(paths, bundle)
        validate_canonical_scheduling(bundle.runtime_program.canonical_scheduling, substances, products)
    except CardLoadError as e:
        errors.append(e.message)
        return _check_failure(errors, info)

    stacks_errors, stacks_info = validate_stacks(paths, product_ids, bundle)
    errors.extend(stacks_errors)
    _append_stack_diagnostics(paths, bundle, stacks_info, info)
    if stacks_errors:
        return _check_failure(errors, info)
    dashboard_files = sorted(paths.dashboards.glob("*.yaml")) if paths.dashboards.exists() else []
    dashboard_errors = check_dashboards(dashboard_files, set(), paths, bundle, substances, info)
    errors.extend(dashboard_errors)
    if dashboard_errors:
        return _check_failure(errors, info)
    return None


def _check_failure(errors: list[str], info: list[str]) -> CheckResult:
    """Report one failed validation boundary and stop downstream work."""
    report(errors, info)
    return CheckResult(exit_code=1, errors=errors, info=info)


def _append_stack_diagnostics(paths: Paths, bundle: OntologyBundle, stacks_info: list[str], info: list[str]) -> None:
    unstacked = [message for message in stacks_info if "has no stack entry" in message]
    info.extend(message for message in stacks_info if message not in unstacked)
    if unstacked:
        product_ids = ", ".join(message.split("product '", 1)[1].split("'", 1)[0] for message in unstacked)
        info.append(
            f"{paths.stacks_file}: {len(unstacked)} tracked product(s) have no stack entry "
            f"({product_ids}); add them to `{bundle.runtime_program.glue_contract.inactive_stack_name}` "
            "if still owned, or leave outside stacks intentionally."
        )
