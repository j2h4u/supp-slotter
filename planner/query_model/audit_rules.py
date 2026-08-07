"""Generated canonical intake-review rule projection."""

from __future__ import annotations

from typing import cast

from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import (
    AUDIT_ASSIGNMENT_CARDINALITY_EXACTLY_ONE,
    AUDIT_ASSIGNMENT_CARDINALITY_ZERO,
    AUDIT_REQUIRED_COVERAGE_ALL_ASSIGNMENT_AXES,
    AUDIT_REQUIRED_COVERAGE_CURRENT_AXIS,
    IMPLEMENTED_AUDIT_ASSIGNMENT_CARDINALITIES,
    IMPLEMENTED_AUDIT_DISPOSITION_CHECK_IDS,
    IMPLEMENTED_AUDIT_DISPOSITION_CHECKS,
    IMPLEMENTED_AUDIT_REQUIRED_COVERAGES,
)

AUDIT_DISPOSITION_CHECKS = IMPLEMENTED_AUDIT_DISPOSITION_CHECKS
AUDIT_DISPOSITION_CHECK_IDS = frozenset(IMPLEMENTED_AUDIT_DISPOSITION_CHECK_IDS)


def load_audit_review_rules(
    ontology_bundle: OntologyBundle,
    *,
    include_retired: bool = False,
) -> list[dict[str, object]]:
    load_audit_disposition_checks(ontology_bundle)
    raw = ontology_bundle.runtime_vocabulary.get("audit_review_rules")
    if not isinstance(raw, list):
        raise RuntimeError("generated ontology has no audit_review_rules")
    assignment_axes = frozenset(row.axis for row in ontology_bundle.runtime_program.assignment_axes)
    rules: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("generated audit_review_rules entries must be mappings")
        rule = cast(dict[str, object], item)
        status = rule.get("status")
        if not isinstance(status, str):
            raise RuntimeError("generated audit review rule status must be a lifecycle state")
        lifecycle = ontology_bundle.runtime_program.lifecycle_decision(status)
        if lifecycle is None:
            raise RuntimeError(f"generated audit review rule status {status!r} is not a runtime lifecycle state")
        if not lifecycle.executable and not include_retired:
            continue
        priority = rule.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0:
            raise RuntimeError("generated audit review rule priority must be a non-negative integer")
        if not isinstance(rule.get("message"), str) or not isinstance(rule.get("action"), str):
            raise RuntimeError("generated audit review rule message/action must be strings")
        if not isinstance(rule.get("enforcement"), str) or not isinstance(rule.get("scope"), dict):
            raise RuntimeError("generated audit review rule governance is incomplete")
        if rule.get("axis") not in assignment_axes:
            raise RuntimeError("generated audit review rule axis must be valid")
        if rule.get("predicate") != "reviewed_disposition_present":
            raise RuntimeError("generated audit review rule predicate must be reviewed_disposition_present")
        subjects = rule.get("subjects")
        if not isinstance(subjects, dict):
            raise RuntimeError("generated audit review rule subjects must be a sorted mapping")
        subject_mapping = cast(dict[str, object], subjects)
        if list(subject_mapping) != sorted(subject_mapping):
            raise RuntimeError("generated audit review rule subjects must be a sorted mapping")
        checks = rule.get("disposition_checks")
        if not isinstance(checks, dict):
            raise RuntimeError("generated audit review rule disposition_checks must be a mapping")
        check_mapping = cast(dict[object, object], checks)
        if not set(check_mapping) <= set(AUDIT_DISPOSITION_CHECKS):
            raise RuntimeError("generated audit review rule disposition_checks have unsupported dispositions")
        if not all(
            isinstance(disposition, str) and isinstance(check_id, str) and check_id in AUDIT_DISPOSITION_CHECK_IDS
            for disposition, check_id in check_mapping.items()
        ):
            raise RuntimeError("generated audit review rule disposition_checks have unsupported checks")
        rules.append(rule)
    return rules


def load_audit_disposition_checks(ontology_bundle: OntologyBundle) -> dict[str, dict[str, object]]:
    """Load the authored semantics for the implemented disposition checkers."""

    raw = ontology_bundle.runtime_vocabulary.get("audit_disposition_checks")
    if not isinstance(raw, dict):
        raise RuntimeError("generated ontology has no audit_disposition_checks")
    checks: dict[str, dict[str, object]] = {}
    for check_id, item in raw.items():
        if not isinstance(check_id, str) or check_id not in AUDIT_DISPOSITION_CHECK_IDS or not isinstance(item, dict):
            raise RuntimeError("generated audit disposition checks are unsupported")
        record = cast(dict[str, object], item)
        if set(record) - {"assignment_cardinality", "required_coverage"}:
            raise RuntimeError(f"generated audit disposition check {check_id!r} has unsupported fields")
        cardinality = record.get("assignment_cardinality")
        coverage = record.get("required_coverage")
        if (
            cardinality not in IMPLEMENTED_AUDIT_ASSIGNMENT_CARDINALITIES
            or coverage not in IMPLEMENTED_AUDIT_REQUIRED_COVERAGES
        ):
            raise RuntimeError(f"generated audit disposition check {check_id!r} has invalid semantics")
        if (
            cardinality == AUDIT_ASSIGNMENT_CARDINALITY_EXACTLY_ONE
            and coverage != AUDIT_REQUIRED_COVERAGE_ALL_ASSIGNMENT_AXES
        ):
            raise RuntimeError(f"generated audit disposition check {check_id!r} exactly_one requires all-axis coverage")
        if cardinality == AUDIT_ASSIGNMENT_CARDINALITY_ZERO and coverage != AUDIT_REQUIRED_COVERAGE_CURRENT_AXIS:
            raise RuntimeError(f"generated audit disposition check {check_id!r} zero requires current-axis coverage")
        checks[check_id] = record
    if set(checks) != AUDIT_DISPOSITION_CHECK_IDS:
        raise RuntimeError("generated audit disposition checks must cover implemented checkers")
    return checks


def load_audit_relation_exemptions(ontology_bundle: OntologyBundle) -> list[dict[str, object]]:
    raw = ontology_bundle.runtime_vocabulary.get("audit_relation_exemptions")
    if not isinstance(raw, list):
        raise RuntimeError("generated ontology has no audit_relation_exemptions")
    exemptions: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("generated audit relation exemption entries must be mappings")
        exemption = cast(dict[str, object], item)
        for key in ("id", "relation_type", "source_selector_key", "target_selector_key"):
            if not isinstance(exemption.get(key), str) or not exemption[key]:
                raise RuntimeError(f"generated audit relation exemption {key} must be a non-empty string")
        exemptions.append(exemption)
    return exemptions
