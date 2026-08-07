"""Deep card-quality audit queries for the SurrealDB read model."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Product, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import relation_endpoint_selector_kind
from planner.ontology.substance_fields import schedule_assignment_fields
from planner.query_model.audit_rules import (
    AUDIT_DISPOSITION_CHECK_IDS,
    AUDIT_DISPOSITION_CHECKS,
    load_audit_disposition_checks,
    load_audit_review_rules,
)
from planner.query_model.session import SurrealSession, id_str, string_list


def collect_full_audit_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
    products: dict[str, Product],
    ontology_bundle: OntologyBundle,
) -> dict[str, list[str]]:
    """Return deep-audit sections for `planner audit --full`.

    Substance display uses the in-memory `substances` map for the formatted name
    (`format_substance_name` reads `Substance.form`, which we'd otherwise have to
    re-format from the db row).
    """
    product_substance_refs = _product_substance_refs(db)
    no_form_unreferenced, no_form_used = _no_form_variant_sections(
        db,
        product_substance_refs,
    )
    missing_classification, missing_intake = _missing_substance_fields(
        db,
        substances,
        product_substance_refs,
        ontology_bundle,
    )
    return {
        "full.no_form_unreferenced": no_form_unreferenced,
        "full.no_form_used": no_form_used,
        "full.no_classification": missing_classification,
        "full.no_intake": missing_intake,
        "full.intake_review": _intake_review(db, substances, ontology_bundle),
        "full.relations_integrity": _relation_integrity_errors(db),
        "full.scheduling_constraints": _scheduling_constraint_coverage(db, ontology_bundle),
        "full.active_product_source": _active_product_source_gaps(
            db,
            products,
            ontology_bundle.runtime_program.glue_contract.inactive_stack_name,
        ),
        "full.policy_governance": _policy_governance(ontology_bundle, include_retired=True),
        "full.assignment_governance": _assignment_governance(
            substances,
            ontology_bundle,
            include_retired=True,
        ),
    }


def _product_substance_refs(db: SurrealSession) -> set[str]:
    refs: set[str] = set()
    for row in db.query("SELECT components FROM product"):
        refs.update(string_list(row.get("components")))
    return refs


def _no_form_variant_sections(
    db: SurrealSession,
    product_substance_refs: set[str],
) -> tuple[list[str], list[str]]:
    by_name: dict[str, list[tuple[str, str | None]]] = {}
    for row in db.query("SELECT id, name, form FROM substance"):
        sid = id_str(row["id"])
        form = row.get("form")
        by_name.setdefault(cast(str, row["name"]), []).append((sid, form if isinstance(form, str) else None))

    no_form_unreferenced: list[str] = []
    no_form_used: list[str] = []
    for name, entries in sorted(by_name.items()):
        no_form = [sid for sid, form in entries if not form]
        with_form = [(sid, form) for sid, form in entries if form]
        if not no_form or not with_form:
            continue
        form_list = ", ".join(sorted(str(f) for _, f in with_form))
        for sid in no_form:
            line = f"{name} ({sid}) - forms: {form_list}"
            if sid in product_substance_refs:
                no_form_used.append(line)
            else:
                no_form_unreferenced.append(line)
    return no_form_unreferenced, no_form_used


def _missing_substance_fields(
    db: SurrealSession,
    substances: dict[str, Substance],
    product_substance_refs: set[str],
    ontology_bundle: OntologyBundle,
) -> tuple[list[str], list[str]]:
    identity_fields = _identity_classification_fields(ontology_bundle)
    primary_assignment_field = _primary_assignment_field(ontology_bundle)
    sub_rows = list(db.query("SELECT id, name FROM substance"))
    missing_classification: list[str] = []
    missing_intake: list[str] = []
    for row in sorted(sub_rows, key=lambda r: cast(str, r["name"]).casefold()):
        sid = id_str(row["id"])
        substance = substances.get(sid)
        if substance is None:
            continue
        display = format_substance_name(substance)
        if any(not cast(tuple[str, ...], getattr(substance, field, ())) for field in identity_fields):
            missing_classification.append(f"{display} ({sid})")
        primary_assignment = cast(tuple[str, ...], getattr(substance, primary_assignment_field, ()))
        if sid in product_substance_refs and not primary_assignment:
            missing_intake.append(f"{display} ({sid})")
    return missing_classification, missing_intake


def _identity_classification_fields(ontology_bundle: OntologyBundle) -> tuple[str, ...]:
    categories = ontology_bundle.runtime_vocabulary.get("categories")
    if not isinstance(categories, dict):
        raise ValueError("ontology runtime_vocabulary.categories must be a mapping")
    fields: list[str] = []
    for category, raw_metadata in categories.items():
        if not isinstance(category, str) or not isinstance(raw_metadata, dict):
            continue
        metadata = cast(dict[str, object], raw_metadata)
        if metadata.get("ontoclean_profile") == "rigid_identity":
            fields.append(category)
    if not fields:
        raise ValueError("ontology runtime_vocabulary.categories declares no rigid identity categories")
    return tuple(fields)


def _primary_assignment_field(ontology_bundle: OntologyBundle) -> str:
    primary = min(ontology_bundle.runtime_program.assignment_axes, key=lambda row: (row.order, row.id))
    return primary.assignment_field


def _intake_review(
    db: SurrealSession,
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
) -> list[str]:
    matches: list[tuple[int, str, str, str, str]] = []
    rows = db.query("SELECT id, name FROM substance")
    rows_by_id = {id_str(row["id"]): row for row in rows}
    for rule in load_audit_review_rules(ontology_bundle):
        subjects = cast(dict[str, object], rule.get("subjects") or {})
        axis = cast(str, rule["axis"])
        for sid, disposition in subjects.items():
            _validate_intake_disposition(rule, disposition, ontology_bundle)
            row = rows_by_id.get(sid)
            substance = substances.get(sid)
            db_name = row.get("name") if row is not None else None
            sort_name = (
                db_name
                if isinstance(db_name, str) and db_name
                else substance.name
                if substance is not None and substance.name
                else sid
            )
            display_name = (
                format_substance_name(substance)
                if substance is not None
                else db_name
                if isinstance(db_name, str) and db_name
                else sid
            )
            if row is None or substance is None:
                matches.append((
                    cast(int, rule["priority"]),
                    sort_name.casefold(),
                    str(rule["id"]),
                    sid,
                    _intake_disposition_message(display_name, sid, rule),
                ))
                continue
            valid = _intake_disposition_valid(disposition, substance, ontology_bundle, axis, rule)
            if not valid:
                matches.append((
                    cast(int, rule["priority"]),
                    sort_name.casefold(),
                    str(rule["id"]),
                    sid,
                    _intake_disposition_message(display_name, sid, rule),
                ))
    return [message for _, _, _, _, message in sorted(matches)]


def _intake_disposition_valid(
    disposition: object,
    substance: Substance,
    ontology_bundle: OntologyBundle,
    axis: str,
    rule: dict[str, object],
) -> bool:
    checker = _intake_disposition_checker(disposition, rule, ontology_bundle)
    return checker(substance, ontology_bundle, axis)


def _validate_intake_disposition(rule: dict[str, object], disposition: object, ontology_bundle: OntologyBundle) -> None:
    _intake_disposition_checker(disposition, rule, ontology_bundle)


def _intake_disposition_checker(
    disposition: object,
    rule: dict[str, object],
    ontology_bundle: OntologyBundle,
) -> Callable[[Substance, OntologyBundle, str], bool]:
    rule_id = str(rule["id"])
    record = cast(dict[str, object], disposition) if isinstance(disposition, dict) else {}
    disposition_id = record.get("disposition")
    if not isinstance(disposition_id, str):
        raise ValueError(f"audit rule {rule_id!r} has an invalid subject disposition")
    disposition_checks = rule.get("disposition_checks")
    if not isinstance(disposition_checks, dict):
        raise ValueError(f"audit rule {rule_id!r} has no disposition checks")
    typed_disposition_checks = cast(dict[str, object], disposition_checks)
    if not set(typed_disposition_checks) <= set(AUDIT_DISPOSITION_CHECKS):
        raise ValueError(f"audit rule {rule_id!r} has unsupported disposition checks")
    check_id = typed_disposition_checks.get(disposition_id)
    if not isinstance(check_id, str) or check_id not in AUDIT_DISPOSITION_CHECK_IDS:
        raise ValueError(f"audit rule {rule_id!r} has unsupported disposition {disposition_id!r}")
    checker = _INTAKE_DISPOSITION_CHECKERS.get(check_id)
    if checker is None:
        raise ValueError(f"audit rule {rule_id!r} has unsupported disposition check {check_id!r}")
    check_policy = load_audit_disposition_checks(ontology_bundle)
    semantics = check_policy.get(check_id)
    if semantics is None:
        raise ValueError(f"audit rule {rule_id!r} has no authored semantics for check {check_id!r}")
    return lambda substance, ontology_bundle, axis: checker(substance, ontology_bundle, axis, semantics)


def _intake_disposition_message(name: str, subject_id: str, rule: dict[str, object]) -> str:
    return f"{name} ({subject_id}): {rule['message']} [{rule['id']}]; {rule['action']}"


def _assignment_values(substance: Substance, ontology_bundle: OntologyBundle) -> dict[str, tuple[str, ...]]:
    return {
        field: cast(tuple[str, ...], getattr(substance, field, ()))
        for field in schedule_assignment_fields(ontology_bundle)
    }


def _has_valid_governed_assignment(
    substance: Substance,
    ontology_bundle: OntologyBundle,
    axis: str,
    semantics: dict[str, object],
) -> bool:
    assignment_values = _assignment_values(substance, ontology_bundle)
    axis_values = assignment_values.get(axis, ())
    cardinality = semantics["assignment_cardinality"]
    if cardinality == "zero":
        return not axis_values
    if cardinality != "exactly_one" or len(axis_values) != 1:
        return False
    template = semantics.get("governance_key_template")
    if not isinstance(template, str):
        return False
    governed_key = template.format(axis=axis, value=axis_values[0])
    expected_keys = {
        f"{schedule_axis}:{slug}" for schedule_axis, values in assignment_values.items() for slug in values
    }
    coverage = semantics["required_coverage"]
    if coverage == "all_assignment_axes":
        return governed_key in substance.schedule_governance and set(substance.schedule_governance) == expected_keys
    if coverage == "current_axis":
        return governed_key in substance.schedule_governance
    return False


def _has_reviewed_no_assignment(
    substance: Substance,
    ontology_bundle: OntologyBundle,
    axis: str,
    semantics: dict[str, object],
) -> bool:
    return _has_valid_governed_assignment(substance, ontology_bundle, axis, semantics)


_INTAKE_DISPOSITION_CHECKERS: dict[str, Callable[[Substance, OntologyBundle, str, dict[str, object]], bool]] = {
    "governed_assignment_exact": _has_valid_governed_assignment,
    "reviewed_no_assignment_empty": _has_reviewed_no_assignment,
}


def _policy_governance(ontology_bundle: OntologyBundle, *, include_retired: bool) -> list[str]:
    vocabulary = ontology_bundle.runtime_vocabulary
    policies = vocabulary.get("scheduling_policies")
    rules = load_audit_review_rules(ontology_bundle, include_retired=include_retired)
    records: list[tuple[str, dict[str, object]]] = []
    if isinstance(policies, dict):
        records.extend(
            (key, cast(dict[str, object], value))
            for key, value in policies.items()
            if isinstance(key, str) and isinstance(value, dict)
        )
    records.extend((str(rule["id"]), rule) for rule in rules)
    lines: list[str] = []
    for key, record in sorted(records):
        status = str(record.get("status", ""))
        lifecycle = ontology_bundle.runtime_program.lifecycle_decision(status)
        if lifecycle is None:
            raise ValueError(f"unknown runtime lifecycle state {status!r} in governance record {key!r}")
        if not lifecycle.executable and not include_retired:
            continue
        evidence = record.get("evidence") or []
        scope = cast(object, record.get("scope") or {})
        lines.append(
            f"{key}: status={status}; enforcement={record.get('enforcement', 'none')}; "
            f"scope={_scope_text(scope)}; evidence={evidence!r}; owner={record.get('owner', '')}; "
            f"review_by={record.get('review_by', '')}; governance={_governance_label(ontology_bundle, status, record.get('enforcement'))}"
        )
    return lines


def _assignment_governance(
    substances: dict[str, Substance],
    ontology_bundle: OntologyBundle,
    *,
    include_retired: bool,
) -> list[str]:
    lines: list[str] = []
    for substance_id, substance in sorted(substances.items()):
        for key, value in sorted(substance.schedule_governance.items()):
            status = value.status
            lifecycle = ontology_bundle.runtime_program.lifecycle_decision(status)
            if lifecycle is None:
                raise ValueError(f"unknown runtime lifecycle state {status!r} in assignment governance {key!r}")
            if not lifecycle.executable and not include_retired:
                continue
            evidence = [
                {"source": row.source, "supports": row.supports, "limitations": row.limitations}
                for row in value.evidence
            ]
            lines.append(
                f"{substance_id} {key}: status={status}; enforcement_cap={value.enforcement_cap}; "
                f"scope={_scope_text(dict(value.scope))}; evidence={evidence!r}; "
                f"owner={value.owner}; review_by={value.review_by}; "
                f"governance={_governance_label(ontology_bundle, status, value.enforcement_cap)}"
            )
    return lines


def _scope_text(scope: object) -> str:
    if not isinstance(scope, dict):
        return "{}"
    mapping = cast(dict[str, object], scope)
    return ",".join(f"{key}={mapping[key]}" for key in sorted(mapping))


def _governance_label(ontology_bundle: OntologyBundle, status: str, enforcement: object) -> str:
    """Render the effective mode from the authored lifecycle degradation matrix."""
    if not isinstance(enforcement, str):
        raise ValueError(f"governance enforcement must be a runtime mode, got {enforcement!r}")
    runtime = ontology_bundle.runtime_program
    if runtime.lifecycle_decision(status) is None or runtime.enforcement_decision(enforcement) is None:
        raise ValueError(f"unknown runtime governance pair {(status, enforcement)!r}")
    degradation = next(
        (
            row
            for row in runtime.projection.degradation
            if row.lifecycle_state == status and row.incoming_mode == enforcement
        ),
        None,
    )
    if degradation is None:
        raise ValueError(f"runtime governance pair {(status, enforcement)!r} has no degradation rule")
    effective = runtime.enforcement_decision(degradation.effective_mode)
    if effective is None:
        raise ValueError(f"runtime degradation rule {degradation.id!r} has unknown effective mode")
    return effective.mode


def _relation_integrity_errors(_db: SurrealSession) -> list[str]:
    """Canonical selector integrity is enforced before read-model construction."""
    return []


def _scheduling_constraint_coverage(db: SurrealSession, ontology_bundle: OntologyBundle) -> list[str]:
    """Render canonical constraint structure and deterministic selector coverage."""
    rows = db.query("SELECT * FROM scheduling_constraint ORDER BY id")
    return [
        _scheduling_constraint_line(row, ontology_bundle)
        for row in sorted(rows, key=lambda row: id_str(row.get("id", "")))
    ]


def _scheduling_constraint_line(row: dict[str, object], ontology_bundle: OntologyBundle) -> str:
    unresolved: list[str] = []
    if not string_list(row.get("src_substances")):
        unresolved.append("source")
    if not string_list(row.get("tgt_substances")):
        unresolved.append("target")
    coverage = f"UNRESOLVED[{','.join(unresolved)}]" if unresolved else "resolved"
    status = str(row.get("status", ""))
    enforcement = str(row.get("enforcement", ""))
    runtime = ontology_bundle.runtime_program
    lifecycle = next(
        (item for item in runtime.constraint_governance.lifecycle_states if item.state == status),
        None,
    )
    enforcement_row = next(
        (item for item in runtime.constraint_governance.enforcement_modes if item.mode == enforcement),
        None,
    )
    if lifecycle is None or enforcement_row is None:
        raise ValueError(f"unknown runtime constraint governance pair {(status, enforcement)!r}")
    # Constraint governance has its own enforcement vocabulary; expose the
    # authored mode rather than maintaining a second label table here.
    governance = enforcement_row.mode
    provenance = (
        f"status={row.get('status', '')}; owner={row.get('owner', '')}; review_by={row.get('review_by', '')}; "
        f"assertion_type={row.get('assertion_type', '')}; "
        f"evidence={string_list(row.get('evidence'))!r}"
    )
    return (
        f"{id_str(row['id'])}: selectors={_selector_text(row.get('src_selector'))}"
        f"->{_selector_text(row.get('tgt_selector'))}; "
        f"source={_selector_text(row.get('src_selector'))}; target={_selector_text(row.get('tgt_selector'))}; "
        f"operation={row.get('operation', '')}; "
        f"enforcement={row.get('enforcement', '')}; coverage={coverage}; {provenance}; "
        f"rationale={row.get('rationale', '')}; semantic_note={row.get('semantic_note', '')}; "
        f"action={row.get('action', '')}; governance={governance}"
    )


def _selector_text(value: object) -> str:
    kind = relation_endpoint_selector_kind(value)
    selector = cast(dict[str, object], value)
    if kind == "entity":
        key = "id" if selector.get("id") else "name"
        return f"entity:{key}={selector.get(key, '')}"
    if kind != "term":
        raise ValueError(f"unsupported relation selector kind {kind!r}")
    return f"term:{selector.get('category', '')}={selector.get('term', '')}"


def _active_product_source_gaps(
    db: SurrealSession,
    products: dict[str, Product],
    inactive_stack_name: str,
) -> list[str]:
    active_product_ids = _active_product_ids(db, inactive_stack_name)
    messages: list[str] = []
    for product_id in sorted(
        active_product_ids,
        key=lambda pid: format_product_name(products[pid]).casefold() if pid in products else pid,
    ):
        product = products.get(product_id)
        if product is None:
            continue
        gaps = _product_source_gaps(product)
        if not gaps:
            continue
        messages.append(f"{format_product_name(product)} ({product_id}): {'; '.join(gaps)}")
    return messages


def _active_product_ids(db: SurrealSession, inactive_stack_name: str) -> set[str]:
    product_ids: set[str] = set()
    for row in db.query("SELECT name, products FROM stack"):
        if row.get("name") == inactive_stack_name:
            continue
        product_ids.update(cast("list[str]", row.get("products") or []))
    return product_ids


def _product_source_gaps(product: Product) -> list[str]:
    gaps: list[str] = []
    if product.brand is None or product.brand == "unknown":
        gaps.append("no brand")
    if not product.urls:
        gaps.append("no urls")
    if product.notes is None:
        gaps.append("no product notes")
    return gaps
