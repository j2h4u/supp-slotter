"""Audit queries for the SurrealDB-backed planner read model.

Set-difference arithmetic stays in Python where it is clearer. SurrealQL owns
the cross-reference collection across heterogeneous sources: product
components, resolved relation endpoints, substance prefer_with arrays, and
dashboard from_traits resolution.

`similar_names` stays in Python because it depends on SequenceMatcher fuzzy
matching, which has no native SurrealQL equivalent.
"""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from planner.cards.substance import format_substance_name
from planner.cards.substance_similarity import collect_similar_substances
from planner.contracts import Substance
from planner.query_model.session import SurrealSession, id_str

_SCHEDULING_NAMESPACES = frozenset({"intake", "timing", "activity"})
_EFFECT_USAGE_REVIEW_MIN_SUBSTANCES = 3


def collect_cleanup_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> dict[str, list[str]]:
    """Return cleanup-candidate sections for `planner audit`."""
    all_substance_ids = {id_str(row["id"]) for row in db.query("SELECT id FROM substance")}

    # --- Substance references built from three heterogeneous sources ---
    product_substance_refs: set[str] = set()
    for row in db.query("SELECT components FROM product"):
        product_substance_refs.update(row.get("components") or [])

    prefer_with_refs: set[str] = set()
    for row in db.query(
        "SELECT id, prefer_with FROM substance WHERE array::len(prefer_with) > 0"
    ):
        prefer_with_refs.add(id_str(row["id"]))
        prefer_with_refs.update(row.get("prefer_with") or [])

    relation_refs: set[str] = set()
    for row in db.query("SELECT src_substances, tgt_substances FROM relation"):
        relation_refs.update(row.get("src_substances") or [])
        relation_refs.update(row.get("tgt_substances") or [])

    knowledge_only_substances = [
        _format_substance_audit_entry(substances[substance_id])
        for substance_id in sorted(
            all_substance_ids - product_substance_refs - prefer_with_refs - relation_refs
        )
        if substance_id in substances
    ]

    # --- Products without stack ---
    all_product_ids = {id_str(row["id"]) for row in db.query("SELECT id FROM product")}
    stack_products: set[str] = set()
    for row in db.query("SELECT products FROM stack"):
        stack_products.update(row.get("products") or [])
    products_without_stack = sorted(all_product_ids - stack_products)

    # --- Unused review traits (trait def with no substance carrying it) ---
    review_trait_ids: set[str] = set()
    for row in db.query("SELECT id, namespace FROM trait"):
        if row.get("namespace") in _SCHEDULING_NAMESPACES:
            continue
        review_trait_ids.add(id_str(row["id"]))
    trait_refs: set[str] = set()
    for row in db.query(
        "SELECT trait_refs FROM substance WHERE array::len(trait_refs) > 0"
    ):
        trait_refs.update(row.get("trait_refs") or [])
    unused_traits = sorted(review_trait_ids - trait_refs)

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
        "substances.knowledge_only": knowledge_only_substances,
        "products.without_stack": products_without_stack,
        "traits.unused": unused_traits,
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": similar_names,
        "relations.name_fanout": _collect_relation_name_fanout_messages(db),
        "dashboard.empty_cluster": empty_cluster_messages,
        "effects.overlap_review": _collect_effect_overlap_messages(db),
    }


def _collect_relation_name_fanout_messages(db: SurrealSession) -> list[str]:
    names_by_id: dict[str, str] = {
        id_str(row["id"]): cast(str, row["name"])
        for row in db.query("SELECT id, name FROM substance")
    }
    messages: list[str] = []
    for row in db.query(
        "SELECT type, src_name_raw, src_substances, tgt_name_raw, tgt_substances "
        "FROM relation"
    ):
        rel_type = cast(str, row["type"])
        messages.extend(
            _relation_name_fanout_side_messages(
                rel_type=rel_type,
                side="source",
                name=row.get("src_name_raw"),
                substance_ids=cast("list[str]", row.get("src_substances") or []),
                names_by_id=names_by_id,
            )
        )
        messages.extend(
            _relation_name_fanout_side_messages(
                rel_type=rel_type,
                side="target",
                name=row.get("tgt_name_raw"),
                substance_ids=cast("list[str]", row.get("tgt_substances") or []),
                names_by_id=names_by_id,
            )
        )
    return messages


def _relation_name_fanout_side_messages(
    *,
    rel_type: str,
    side: str,
    name: object,
    substance_ids: list[str],
    names_by_id: dict[str, str],
) -> list[str]:
    if not isinstance(name, str) or len(substance_ids) <= 1:
        return []
    endpoint = f"{side}_name"
    matched = [
        f"{names_by_id.get(substance_id, substance_id)} ({substance_id})"
        for substance_id in sorted(substance_ids)
    ]
    return [
        f"{rel_type} {endpoint} '{name}' matches {len(substance_ids)} substance cards: "
        f"{', '.join(matched)}. Keep the name endpoint only when the all-form "
        f"match is intentional; otherwise use {side}_substance."
    ]


def _collect_effect_overlap_messages(db: SurrealSession) -> list[str]:
    """Return non-blocking review hints for potentially overlapping effect axes."""
    effect_labels: dict[str, str] = {}
    for row in db.query("SELECT namespace, short_name, label FROM trait"):
        if row.get("namespace") != "effect":
            continue
        short_name = cast(str, row["short_name"])
        effect_labels[short_name] = cast(str, row["label"])

    messages: list[str] = []
    messages.extend(_same_stem_effect_messages(effect_labels))
    messages.extend(_same_usage_effect_messages(db, effect_labels))
    return messages


def _same_stem_effect_messages(effect_labels: dict[str, str]) -> list[str]:
    by_stem: dict[str, list[str]] = defaultdict(list)
    for slug in effect_labels:
        by_stem[_effect_overlap_stem(slug)].append(slug)

    messages: list[str] = []
    for _stem, slugs in sorted(by_stem.items()):
        if len(slugs) < 2:
            continue
        messages.append(
            "Same-stem effect slugs: "
            f"{', '.join(sorted(slugs))}. "
            "Review whether these are distinct facts or should be merged."
        )
    return messages


def _same_usage_effect_messages(
    db: SurrealSession,
    effect_labels: dict[str, str],
) -> list[str]:
    usage_by_effect: dict[str, set[str]] = defaultdict(set)
    names_by_id: dict[str, str] = {}
    for row in db.query("SELECT id, name, effect FROM substance"):
        substance_id = id_str(row["id"])
        names_by_id[substance_id] = cast(str, row["name"])
        effect_slugs = cast("list[str]", row.get("effect") or [])
        for slug in effect_slugs:
            if slug in effect_labels:
                usage_by_effect[slug].add(substance_id)

    by_usage: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for slug, substance_ids in usage_by_effect.items():
        by_usage[tuple(sorted(substance_ids))].append(slug)

    messages: list[str] = []
    for substance_ids, slugs in sorted(by_usage.items()):
        if len(slugs) < 2 or len(substance_ids) < _EFFECT_USAGE_REVIEW_MIN_SUBSTANCES:
            continue
        substance_names = [
            f"{substance_id} {names_by_id[substance_id]}"
            for substance_id in substance_ids
        ]
        messages.append(
            f"Same effect usage across {len(substance_ids)} substances "
            f"({', '.join(substance_names)}): {', '.join(sorted(slugs))}. "
            "Review whether these facts stay independent as coverage expands."
        )
    return messages


def _effect_overlap_stem(slug: str) -> str:
    parts = slug.split("_")
    suffixes = {"context", "support", "modulation", "cofactor"}
    while parts and parts[-1] in suffixes:
        parts.pop()
    aliases = {
        "metabolic": "metabolism",
    }
    return "_".join(aliases.get(part, part) for part in parts)


def _format_substance_audit_entry(substance: Substance) -> str:
    return f"{format_substance_name(substance)} ({substance.id})"
