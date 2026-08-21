"""Deep card-quality audit queries for the SurrealDB read model."""

from __future__ import annotations

from typing import cast

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

    Full audit is deliberately limited to generic source/selector assertions.
    Scheduler classification and assignment axes are execution concerns, not
    Python-owned audit rules.
    """
    del substances
    del products
    product_substance_refs = _product_substance_refs(db)
    no_form_unreferenced, no_form_used = _no_form_variant_sections(
        db,
        product_substance_refs,
    )
    return {
        "diagnostics": [
            *no_form_unreferenced,
            *no_form_used,
            *_relation_integrity_errors(db),
            *_scheduling_constraint_coverage(db, ontology_bundle),
        ]
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
