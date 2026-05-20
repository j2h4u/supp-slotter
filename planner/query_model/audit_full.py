"""Deep card-quality audit queries for the SurrealDB read model."""

from __future__ import annotations

from typing import cast

from planner.cards.substance import format_substance_name
from planner.contracts import Substance
from planner.query_model.session import SurrealSession, id_str

# Domain-rule correlations from trait-registry applies_when. NOT hard rules -
# a card that doesn't satisfy these is a prompt for human review.
_INTAKE_REVIEW_HINTS: dict[str, set[str]] = {
    "mineral": {"food_preferred", "food_required"},
    "fat_soluble": {"fat_meal_required", "food_preferred", "food_required"},
}


def collect_full_audit_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> dict[str, list[str]]:
    """Return deep-audit sections for `planner audit --full`.

    Substance display uses the in-memory `substances` map for the formatted name
    (`format_substance_name` reads `Substance.form`, which we'd otherwise have to
    re-format from the db row).
    """
    product_substance_refs = _product_substance_refs(db)
    stubs_orphan, stubs_used = _stub_sections(db, product_substance_refs)
    missing_classification, missing_intake = _missing_substance_fields(db, substances)
    return {
        "full.stubs_orphan": stubs_orphan,
        "full.stubs_used": stubs_used,
        "full.no_classification": missing_classification,
        "full.no_intake": missing_intake,
        "full.intake_review": _intake_review(db, substances),
        "full.relations_integrity": _relation_integrity_errors(db),
    }


def _product_substance_refs(db: SurrealSession) -> set[str]:
    refs: set[str] = set()
    for row in db.query("SELECT components FROM product"):
        refs.update(row.get("components") or [])
    return refs


def _stub_sections(
    db: SurrealSession,
    product_substance_refs: set[str],
) -> tuple[list[str], list[str]]:
    by_name: dict[str, list[tuple[str, str | None]]] = {}
    for row in db.query("SELECT id, name, form FROM substance"):
        sid = id_str(row["id"])
        by_name.setdefault(cast(str, row["name"]), []).append((sid, row.get("form")))

    stubs_orphan: list[str] = []
    stubs_used: list[str] = []
    for name, entries in sorted(by_name.items()):
        no_form = [sid for sid, form in entries if not form]
        with_form = [(sid, form) for sid, form in entries if form]
        if not no_form or not with_form:
            continue
        form_list = ", ".join(sorted(str(f) for _, f in with_form))
        for sid in no_form:
            line = f"{name} ({sid}) - forms: {form_list}"
            if sid in product_substance_refs:
                stubs_used.append(line)
            else:
                stubs_orphan.append(line)
    return stubs_orphan, stubs_used


def _missing_substance_fields(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> tuple[list[str], list[str]]:
    sub_rows = list(db.query(
        "SELECT id, name FROM substance "
        "WHERE array::len(is_) = 0 "
        "OR array::len(intake) = 0"
    ))
    missing_classification: list[str] = []
    missing_intake: list[str] = []
    for row in sorted(sub_rows, key=lambda r: cast(str, r["name"]).casefold()):
        sid = id_str(row["id"])
        substance = substances.get(sid)
        if substance is None:
            continue
        display = format_substance_name(substance)
        if not substance.is_:
            missing_classification.append(f"{display} ({sid})")
        if not substance.intake:
            missing_intake.append(f"{display} ({sid})")
    return missing_classification, missing_intake


def _intake_review(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> list[str]:
    intake_review: list[str] = []
    for is_slug, acceptable in _INTAKE_REVIEW_HINTS.items():
        rows = db.query(
            "SELECT id, name, is_, intake FROM substance "
            "WHERE $slug IN is_ AND array::len(intake) > 0 "
            "AND intake NONEINSIDE $acceptable",
            {"slug": is_slug, "acceptable": list(acceptable)},
        )
        for row in sorted(rows, key=lambda r: cast(str, r["name"]).casefold()):
            sid = id_str(row["id"])
            substance = substances.get(sid)
            if substance is None:
                continue
            intake_review.append(
                f"{format_substance_name(substance)} ({sid}): is:{is_slug}, "
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
        "SELECT id, name, effect FROM substance "
        "WHERE $slug IN is_ AND array::len(intake) > 0",
        {"slug": "enzyme"},
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
            f"{format_substance_name(substance)} ({sid}): is:enzyme, "
            f"intake:{sorted(substance.intake)} - none of {sorted(acceptable)}"
        )
    return intake_review


def _relation_integrity_errors(db: SurrealSession) -> list[str]:
    name_set: set[str] = {
        cast(str, row["name"]) for row in db.query("SELECT name FROM substance")
    }
    id_set: set[str] = {id_str(row["id"]) for row in db.query("SELECT id FROM substance")}
    relation_errors: list[str] = []
    for row in db.query(
        "SELECT type, src_substance_raw, src_name_raw, tgt_substance_raw, tgt_name_raw "
        "FROM relation"
    ):
        rel_type = cast(str, row["type"])
        src_name = row.get("src_name_raw")
        tgt_name = row.get("tgt_name_raw")
        src_sub = row.get("src_substance_raw")
        tgt_sub = row.get("tgt_substance_raw")
        if isinstance(src_name, str) and src_name not in name_set:
            relation_errors.append(f"unknown source_name '{src_name}' in {rel_type}")
        if isinstance(tgt_name, str) and tgt_name not in name_set:
            relation_errors.append(f"unknown target_name '{tgt_name}' in {rel_type}")
        if isinstance(src_sub, str) and src_sub not in id_set:
            relation_errors.append(f"unknown source_substance '{src_sub}' in {rel_type}")
        if isinstance(tgt_sub, str) and tgt_sub not in id_set:
            relation_errors.append(f"unknown target_substance '{tgt_sub}' in {rel_type}")
    return relation_errors
