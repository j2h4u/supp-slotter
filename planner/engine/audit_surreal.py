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
from planner.cards.substance import collect_similar_substances
from planner.contracts import Substance


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


def collect_cleanup_sections_surreal(
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
