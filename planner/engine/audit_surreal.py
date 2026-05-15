"""SurrealDB-backed `_collect_cleanup_sections` for `planner audit`.

Mirrors planner.engine.audit._collect_cleanup_sections. The set-difference
arithmetic stays in Python — that's already clean. What moves to SurrealQL is
the *reference building* across heterogeneous sources (product components,
relation endpoints with id-OR-name matching, substance prefer_with arrays,
dashboard from_traits resolution) — the part that's verbose by hand.

Output dict shape is identical to the original; equivalence is asserted in
tests/test_poc_surrealdb.py against the canonical Python implementation.

similar_names stays in Python (it depends on SequenceMatcher fuzzy matching,
which has no native SurrealQL equivalent).
"""

from __future__ import annotations

from typing import Any, cast

from surrealdb import RecordID

from planner.cards.relations_surreal import SurrealSession
from planner.cards.substance import collect_similar_substances, format_substance_name
from planner.contracts import Substance

# Domain-rule correlations from traits.yaml applies_when. NOT hard rules —
# a card that doesn't satisfy these is a prompt for human review.
_INTAKE_REVIEW_HINTS: dict[str, set[str]] = {
    "mineral": {"food_preferred", "food_required"},
    "fat_soluble": {"fat_meal_required", "food_required"},
    "enzyme": {"empty_preferred"},
}


def _id_str(value: Any) -> str:
    """Coerce a SurrealDB id field to its bare string.

    SurrealDB wraps the `id` field as `RecordID(table_name, record_id)` on
    return; that object is unhashable and can't go into a set or be compared
    against bare-string ids stored in other fields. The bare string lives at
    `.id` on the RecordID (the repr is misleading — it prints `record_id=…`
    but the attribute is `.id`). Fall through if the value is already a string.
    """
    if isinstance(value, RecordID):
        return cast(str, value.id)
    return cast(str, value)


def collect_cleanup_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> dict[str, list[str]]:
    """Return the cleanup-candidates dict with the same shape as the canonical
    `planner.engine.audit._collect_cleanup_sections`.

    `substances` is passed in only for similar_names (fuzzy matching, Python).
    Every other category is computed via SurrealQL against the db handle.
    """
    all_substance_ids = {_id_str(row["id"]) for row in db.query("SELECT id FROM substance")}

    # --- Substance references built from three heterogeneous sources ---
    product_substance_refs: set[str] = set()
    for row in db.query("SELECT components FROM product"):
        product_substance_refs.update(row.get("components") or [])

    prefer_with_refs: set[str] = set()
    for row in db.query(
        "SELECT id, prefer_with FROM substance WHERE array::len(prefer_with) > 0"
    ):
        prefer_with_refs.add(_id_str(row["id"]))
        prefer_with_refs.update(row.get("prefer_with") or [])

    relation_refs: set[str] = set()
    for row in db.query("SELECT src_substances, tgt_substances FROM relation"):
        relation_refs.update(row.get("src_substances") or [])
        relation_refs.update(row.get("tgt_substances") or [])

    reference_only_substances = sorted(
        all_substance_ids - product_substance_refs - prefer_with_refs - relation_refs
    )

    # --- Products without stack ---
    all_product_ids = {_id_str(row["id"]) for row in db.query("SELECT id FROM product")}
    stack_products: set[str] = set()
    for row in db.query("SELECT products FROM stack"):
        stack_products.update(row.get("products") or [])
    products_without_stack = sorted(all_product_ids - stack_products)

    # --- Unused traits (trait def with no substance carrying it) ---
    all_trait_ids = {_id_str(row["id"]) for row in db.query("SELECT id FROM trait")}
    trait_refs: set[str] = set()
    for row in db.query(
        "SELECT trait_refs FROM substance WHERE array::len(trait_refs) > 0"
    ):
        trait_refs.update(row.get("trait_refs") or [])
    unused_traits = sorted(all_trait_ids - trait_refs)

    # --- Stack-level issues ---
    empty_stacks = sorted(
        cast(str, row["name"])
        for row in db.query(
            "SELECT name FROM stack WHERE array::len(products) == 0"
        )
    )
    all_stack_names: set[str] = {
        cast(str, row["name"]) for row in db.query("SELECT name FROM stack")
    }
    pillbox_stack_names: set[str] = {
        cast(str, row["stack_name"]) for row in db.query("SELECT stack_name FROM pillbox")
    }
    stacks_without_pillboxes = sorted(all_stack_names - pillbox_stack_names - {"inactive"})
    pillboxes_without_stack = sorted(pillbox_stack_names - all_stack_names)

    # --- Empty dashboard clusters (from_traits resolves to zero member substances) ---
    empty_cluster_messages: list[str] = []
    for dash in db.query("SELECT slug, from_traits_pairs FROM dashboard"):
        slug = cast(str, dash["slug"])
        pairs = cast("list[str]", dash.get("from_traits_pairs") or [])
        if pairs:
            members = db.query(
                "SELECT id FROM substance WHERE trait_refs ANYINSIDE $pairs",
                {"pairs": pairs},
            )
            if members:
                continue
        empty_cluster_messages.append(
            f"Empty cluster: data/dashboards/{slug}.yaml from_traits resolves to "
            f"zero member substances (using union resolution: OR across all listed "
            f"(namespace, slug) pairs). Resolution: update from_traits to match "
            f"substance traits, OR remove the dashboard yaml if abandoned."
        )

    # --- Similar names: pure-Python fuzzy match, no SurrealQL equivalent ---
    similar_names = collect_similar_substances(substances)

    return {
        "substances.reference_only": reference_only_substances,
        "products.without_stack": products_without_stack,
        "traits.unused": unused_traits,
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": similar_names,
        "dashboard.empty_cluster": empty_cluster_messages,
    }


def collect_full_audit_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> dict[str, list[str]]:
    """SurrealDB-backed `_collect_full_audit_sections`. Returns the 6 deep-audit
    categories with the same shape as the canonical Python helper.

    Substance display uses the in-memory `substances` map for the formatted name
    (`format_substance_name` reads `Substance.form`, which we'd otherwise have to
    re-format from the db row).
    """
    # Substances referenced by any product — for stub orphan/used partition
    product_substance_refs: set[str] = set()
    for row in db.query("SELECT components FROM product"):
        product_substance_refs.update(row.get("components") or [])

    # --- Stubs: names with BOTH form-less and form-bearing variants ---
    by_name: dict[str, list[tuple[str, str | None]]] = {}
    for row in db.query("SELECT id, name, form FROM substance"):
        sid = _id_str(row["id"])
        by_name.setdefault(cast(str, row["name"]), []).append((sid, row.get("form")))

    stubs_orphan: list[str] = []
    stubs_used: list[str] = []
    for name, entries in sorted(by_name.items()):
        no_form = [sid for sid, form in entries if not form]
        with_form = [(sid, form) for sid, form in entries if form]
        if no_form and with_form:
            form_list = ", ".join(sorted(str(f) for _, f in with_form))
            for sid in no_form:
                line = f"{name} ({sid}) — forms: {form_list}"
                (stubs_used if sid in product_substance_refs else stubs_orphan).append(line)

    # --- Substances missing classification / intake ---
    sub_rows = list(db.query(
        "SELECT id, name FROM substance "
        "WHERE array::len(is_) = 0 "
        "OR array::len(intake) = 0"
    ))
    missing_classification: list[str] = []
    missing_intake: list[str] = []
    for row in sorted(sub_rows, key=lambda r: cast(str, r["name"]).casefold()):
        sid = _id_str(row["id"])
        substance = substances.get(sid)
        if substance is None:
            continue
        display = format_substance_name(substance)
        if not substance.is_:
            missing_classification.append(f"{display} ({sid})")
        if not substance.intake:
            missing_intake.append(f"{display} ({sid})")

    # --- Intake-review hints: per-is_slug rule, find substances whose intake
    # doesn't intersect with the acceptable set ---
    intake_review: list[str] = []
    for is_slug, acceptable in _INTAKE_REVIEW_HINTS.items():
        rows = db.query(
            "SELECT id, name, is_, intake FROM substance "
            "WHERE $slug IN is_ AND array::len(intake) > 0 "
            "AND intake NONEINSIDE $acceptable",
            {"slug": is_slug, "acceptable": list(acceptable)},
        )
        for row in sorted(rows, key=lambda r: cast(str, r["name"]).casefold()):
            sid = _id_str(row["id"])
            substance = substances.get(sid)
            if substance is None:
                continue
            intake_review.append(
                f"{format_substance_name(substance)} ({sid}): is:{is_slug}, "
                f"intake:{sorted(substance.intake)} — none of {sorted(acceptable)}"
            )

    # --- Relations integrity: raw endpoint refs that don't resolve ---
    name_set: set[str] = {cast(str, row["name"]) for row in db.query("SELECT name FROM substance")}
    id_set: set[str] = {_id_str(row["id"]) for row in db.query("SELECT id FROM substance")}
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

    return {
        "full.stubs_orphan": stubs_orphan,
        "full.stubs_used": stubs_used,
        "full.no_classification": missing_classification,
        "full.no_intake": missing_intake,
        "full.intake_review": intake_review,
        "full.relations_integrity": relation_errors,
    }
