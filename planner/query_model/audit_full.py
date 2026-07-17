"""Deep card-quality audit queries for the SurrealDB read model."""

from __future__ import annotations

from typing import cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Product, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.query_model.audit_rules import load_audit_review_rules
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
    )
    return {
        "full.no_form_unreferenced": no_form_unreferenced,
        "full.no_form_used": no_form_used,
        "full.no_classification": missing_classification,
        "full.no_intake": missing_intake,
        "full.intake_review": _intake_review(db, substances, ontology_bundle),
        "full.relations_integrity": _relation_integrity_errors(db),
        "full.scheduling_constraints": _scheduling_constraint_coverage(db),
        "full.active_product_source": _active_product_source_gaps(db, products),
        "full.policy_governance": _policy_governance(ontology_bundle, include_retired=True),
        "full.assignment_governance": _assignment_governance(substances, include_retired=True),
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
) -> tuple[list[str], list[str]]:
    sub_rows = list(db.query("SELECT id, name FROM substance WHERE array::len(kind) = 0 OR array::len(intake) = 0"))
    missing_classification: list[str] = []
    missing_intake: list[str] = []
    for row in sorted(sub_rows, key=lambda r: cast(str, r["name"]).casefold()):
        sid = id_str(row["id"])
        substance = substances.get(sid)
        if substance is None:
            continue
        display = format_substance_name(substance)
        if not substance.kind:
            missing_classification.append(f"{display} ({sid})")
        if sid in product_substance_refs and not substance.intake:
            missing_intake.append(f"{display} ({sid})")
    return missing_classification, missing_intake


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
                    _intake_disposition_message(display_name, sid, str(rule["id"])),
                ))
                continue
            record = cast(dict[str, object], disposition) if isinstance(disposition, dict) else {}
            axis_values: tuple[str, ...] = {
                "intake": substance.intake,
                "timing": substance.timing,
                "activity": substance.activity,
            }[axis]
            expected_keys = {
                f"{schedule_axis}:{slug}"
                for schedule_axis, values in (
                    ("intake", substance.intake),
                    ("timing", substance.timing),
                    ("activity", substance.activity),
                )
                for slug in values
            }
            if record.get("disposition") == "governed_assignment":
                governed_key = f"{axis}:{axis_values[0]}" if len(axis_values) == 1 else None
                valid = (
                    governed_key is not None
                    and governed_key in substance.schedule_governance
                    and set(substance.schedule_governance) == expected_keys
                )
            else:
                valid = record.get("disposition") == "reviewed_no_assignment" and not axis_values
            if not valid:
                matches.append((
                    cast(int, rule["priority"]),
                    sort_name.casefold(),
                    str(rule["id"]),
                    sid,
                    _intake_disposition_message(display_name, sid, str(rule["id"])),
                ))
    return [message for _, _, _, _, message in sorted(matches)]


def _intake_disposition_message(name: str, subject_id: str, rule_id: str) -> str:
    return (
        f"{name} ({subject_id}): explicit intake disposition missing [{rule_id}]; "
        "add a governed assignment or reviewed no-assignment disposition; no intake value inferred"
    )


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
        if status == "retired" and not include_retired:
            continue
        evidence = record.get("evidence") or []
        scope = cast(object, record.get("scope") or {})
        lines.append(
            f"{key}: status={status}; enforcement={record.get('enforcement', 'none')}; "
            f"scope={_scope_text(scope)}; evidence={evidence!r}; owner={record.get('owner', '')}; "
            f"review_by={record.get('review_by', '')}; governance={_governance_label(status, record.get('enforcement'))}"
        )
    return lines


def _assignment_governance(substances: dict[str, Substance], *, include_retired: bool) -> list[str]:
    lines: list[str] = []
    for substance_id, substance in sorted(substances.items()):
        for key, value in sorted(substance.schedule_governance.items()):
            status = value.status
            if status == "retired" and not include_retired:
                continue
            evidence = [
                {"source": row.source, "supports": row.supports, "limitations": row.limitations}
                for row in value.evidence
            ]
            lines.append(
                f"{substance_id} {key}: status={status}; enforcement_cap={value.enforcement_cap}; "
                f"scope={_scope_text(dict(value.scope))}; evidence={evidence!r}; "
                f"owner={value.owner}; review_by={value.review_by}; "
                f"governance={_governance_label(status, value.enforcement_cap)}"
            )
    return lines


def _scope_text(scope: object) -> str:
    if not isinstance(scope, dict):
        return "{}"
    mapping = cast(dict[str, object], scope)
    return ",".join(f"{key}={mapping[key]}" for key in sorted(mapping))


def _governance_label(status: str, enforcement: object) -> str:
    if status == "retired":
        return "archival/non-enforcing"
    if status == "review_pending":
        return "diagnostic-only" if enforcement == "advisory" else "preference-only"
    if enforcement == "advisory":
        return "advisory"
    return "enforcing"


def _relation_integrity_errors(_db: SurrealSession) -> list[str]:
    """Canonical selector integrity is enforced before read-model construction."""
    return []


def _scheduling_constraint_coverage(db: SurrealSession) -> list[str]:
    """Render canonical constraint structure and deterministic selector coverage."""
    rows = db.query("SELECT * FROM scheduling_constraint ORDER BY id")
    return [_scheduling_constraint_line(row) for row in sorted(rows, key=lambda row: id_str(row.get("id", "")))]


def _scheduling_constraint_line(row: dict[str, object]) -> str:
    unresolved: list[str] = []
    if not string_list(row.get("src_substances")):
        unresolved.append("source")
    if not string_list(row.get("tgt_substances")):
        unresolved.append("target")
    coverage = f"UNRESOLVED[{','.join(unresolved)}]" if unresolved else "resolved"
    scope = row.get("scope")
    scope_items: list[tuple[str, str]] = []
    if isinstance(scope, dict):
        for key, value in scope.items():
            if isinstance(key, str) and isinstance(value, str):
                scope_items.append((key, value))
    scope_text = ",".join(f"{key}={value}" for key, value in sorted(scope_items))
    status = str(row.get("status", ""))
    enforcement = str(row.get("enforcement", ""))
    governance_notes: list[str] = []
    if status == "retired":
        governance_notes.append("archival/non-enforcing")
    if enforcement == "review":
        governance_notes.append("diagnostic-only")
    elif status == "approved" and enforcement == "advisory":
        governance_notes.append("soft-scoring")
    governance = ",".join(governance_notes) or "enforcing"
    provenance = (
        f"status={row.get('status', '')}; owner={row.get('owner', '')}; review_by={row.get('review_by', '')}; "
        f"assertion_type={row.get('assertion_type', '')}; legacy_preserved={row.get('legacy_preserved')}; "
        f"legacy_relation_id={row.get('legacy_relation_id', '')}; scope={scope_text}; "
        f"evidence={string_list(row.get('evidence'))!r}"
    )
    return (
        f"{id_str(row['id'])}: selectors={_selector_text(row.get('src_selector'))}"
        f"->{_selector_text(row.get('tgt_selector'))}; "
        f"source={_selector_text(row.get('src_selector'))}; target={_selector_text(row.get('tgt_selector'))}; "
        f"effect={row.get('effect', '')}; "
        f"enforcement={row.get('enforcement', '')}; coverage={coverage}; {provenance}; "
        f"rationale={row.get('rationale', '')}; semantic_note={row.get('semantic_note', '')}; "
        f"action={row.get('action', '')}; governance={governance}"
    )


def _selector_text(value: object) -> str:
    if not isinstance(value, dict):
        return "invalid"
    selector = cast(dict[str, object], value)
    if selector.get("kind") == "entity":
        key = "id" if selector.get("id") else "name"
        return f"entity:{key}={selector.get(key, '')}"
    return f"term:{selector.get('category', '')}={selector.get('term', '')}"


def _active_product_source_gaps(
    db: SurrealSession,
    products: dict[str, Product],
) -> list[str]:
    active_product_ids = _active_product_ids(db)
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


def _active_product_ids(db: SurrealSession) -> set[str]:
    product_ids: set[str] = set()
    for row in db.query("SELECT name, products FROM stack"):
        if row.get("name") == "inactive":
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
