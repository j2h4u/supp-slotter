"""Deep card-quality audit queries for the SurrealDB read model."""

from __future__ import annotations

from typing import cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Product, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.glue_capabilities import relation_endpoint_selector_kind
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
        "full.relations_integrity": _relation_integrity_errors(db),
        "full.scheduling_constraints": _scheduling_constraint_coverage(db, ontology_bundle),
        "full.active_product_source": _active_product_source_gaps(
            db,
            products,
            ontology_bundle.runtime_program.glue_contract.inactive_stack_name,
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
    return (
        f"{id_str(row['id'])}: selectors={_selector_text(row.get('src_selector'))}"
        f"->{_selector_text(row.get('tgt_selector'))}; "
        f"source={_selector_text(row.get('src_selector'))}; target={_selector_text(row.get('tgt_selector'))}; "
        f"operation={row.get('operation', '')}; coverage={coverage}; "
        f"rationale={row.get('rationale', '')}; action={row.get('action', '')}"
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
