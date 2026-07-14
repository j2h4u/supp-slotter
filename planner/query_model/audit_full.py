"""Deep card-quality audit queries for the SurrealDB read model."""

from __future__ import annotations

from typing import cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Product, Substance
from planner.query_model.audit_rules import load_audit_review_rules
from planner.query_model.session import SurrealSession, id_str, string_list


def collect_full_audit_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
    products: dict[str, Product],
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
        "full.intake_review": _intake_review(db, substances),
        "full.relations_integrity": _relation_integrity_errors(db),
        "full.scheduling_constraints": _scheduling_constraint_coverage(db),
        "full.active_product_source": _active_product_source_gaps(db, products),
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
) -> list[str]:
    matches: list[tuple[int, str, str, str]] = []
    rows = db.query("SELECT id, name, kind, quality, effect, intake FROM substance WHERE array::len(intake) > 0")
    for rule in load_audit_review_rules():
        selector = cast(dict[str, object], rule["selector"])
        accepted = set(cast(list[str], rule["accepted_intake"]))
        for row in sorted(rows, key=lambda r: cast(str, r["name"]).casefold()):
            values = set(cast(list[str], row.get(str(selector["field"])) or []))
            if str(selector["contains"]) not in values:
                continue
            condition = selector.get("condition")
            if isinstance(condition, dict):
                condition_fields = cast(dict[str, object], condition)
                effects = set(cast(list[str], row.get("effect") or []))
                contains = condition_fields.get("contains")
                not_contains = condition_fields.get("not_contains")
                if (isinstance(contains, str) and contains not in effects) or (
                    isinstance(not_contains, str) and not_contains in effects
                ):
                    continue
            sid = id_str(row["id"])
            substance = substances.get(sid)
            if substance is not None and not (set(substance.intake) & accepted):
                message = (
                    f"{format_substance_name(substance)} ({sid}): {rule['message']}, "
                    f"intake:{sorted(substance.intake)} - none of {sorted(accepted)}"
                )
                matches.append((
                    cast(int, rule["priority"]),
                    cast(str, row["name"]).casefold(),
                    str(rule["id"]),
                    message,
                ))
    return [message for _, _, _, message in sorted(matches)]


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
