"""Deep card-quality audit queries for the SurrealDB read model."""

from __future__ import annotations

from typing import cast

from planner.cards.product import format_product_name
from planner.cards.substance import format_substance_name
from planner.contracts import Product, Substance
from planner.query_model.session import SurrealSession, id_str, string_list

# Domain-rule correlations from trait-registry applies_when. NOT hard rules -
# a card that doesn't satisfy these is a prompt for human review.
_INTAKE_REVIEW_HINTS: dict[tuple[str, str], set[str]] = {
    ("kind", "mineral"): {"food_preferred", "food_required"},
    ("quality", "fat_soluble"): {"fat_meal_required", "food_preferred", "food_required"},
}


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
    intake_review: list[str] = []
    for (category, term), acceptable in _INTAKE_REVIEW_HINTS.items():
        rows = db.query(
            f"SELECT id, name, {category}, intake FROM substance "
            f"WHERE $term IN {category} AND array::len(intake) > 0 "
            "AND intake NONEINSIDE $acceptable",
            {"term": term, "acceptable": list(acceptable)},
        )
        for row in sorted(rows, key=lambda r: cast(str, r["name"]).casefold()):
            sid = id_str(row["id"])
            substance = substances.get(sid)
            if substance is None:
                continue
            intake_review.append(
                f"{format_substance_name(substance)} ({sid}): {category}:{term}, "
                f"intake:{sorted(substance.intake)} - none of {sorted(acceptable)}"
            )
    intake_review.extend(_enzyme_intake_review(db, substances))
    return intake_review


def _enzyme_intake_review(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> list[str]:
    intake_review: list[str] = []
    rows = db.query(
        "SELECT id, name, effect FROM substance WHERE $term IN kind AND array::len(intake) > 0",
        {"term": "enzyme"},
    )
    for row in sorted(rows, key=lambda r: cast(str, r["name"]).casefold()):
        sid = id_str(row["id"])
        substance = substances.get(sid)
        if substance is None:
            continue
        effect_slugs = set(cast("list[str]", row.get("effect") or []))
        if "digestive_enzyme_context" in effect_slugs:
            acceptable = {"food_preferred", "food_required"}
        else:
            acceptable = {"empty_preferred"}
        if set(substance.intake) & acceptable:
            continue
        intake_review.append(
            f"{format_substance_name(substance)} ({sid}): kind:enzyme, "
            f"intake:{sorted(substance.intake)} - none of {sorted(acceptable)}"
        )
    return intake_review


def _relation_integrity_errors(_db: SurrealSession) -> list[str]:
    """Canonical selector integrity is enforced before read-model construction."""
    return []


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
