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
_CONTEXT_EFFECT_WITHOUT_CONSUMER_MIN_SUBSTANCES = 3


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
        "context.without_dashboard_selector": _collect_context_without_dashboard_selector_messages(
            db
        ),
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": similar_names,
        "dashboard.empty_cluster": empty_cluster_messages,
        "effects.context_without_consumer": _collect_context_effect_without_consumer_messages(
            db
        ),
        "effects.overlap_review": _collect_effect_overlap_messages(db),
    }


def _collect_context_without_dashboard_selector_messages(
    db: SurrealSession,
) -> list[str]:
    """Return context tags that no dashboard consumes."""
    selected_contexts: set[str] = set()
    for row in db.query("SELECT from_traits_pairs FROM dashboard"):
        for pair in cast("list[str]", row.get("from_traits_pairs") or []):
            namespace, _, slug = pair.partition(":")
            if namespace == "context" and slug:
                selected_contexts.add(slug)

    members_by_context: dict[str, list[str]] = defaultdict(list)
    for row in db.query("SELECT id, name, context FROM substance"):
        substance_label = f"{id_str(row['id'])} {cast(str, row['name'])}"
        for slug in cast("list[str]", row.get("context") or []):
            members_by_context[slug].append(substance_label)

    messages: list[str] = []
    for slug, members in sorted(members_by_context.items()):
        if slug in selected_contexts:
            continue
        messages.append(
            f"context:{slug} is carried by {len(members)} substances but no "
            "dashboard from_traits selector consumes it. "
            f"Members: {', '.join(sorted(members))}. "
            "Resolution: remove stale context tags, add a dashboard selector, "
            "or document an explicit exception."
        )
    return messages


def _collect_context_effect_without_consumer_messages(
    db: SurrealSession,
) -> list[str]:
    """Return high-use effect:*_context slugs that no dashboard or relation consumes."""
    consumed_effects: set[str] = set()
    for row in db.query("SELECT from_traits_pairs FROM dashboard"):
        for pair in cast("list[str]", row.get("from_traits_pairs") or []):
            namespace, _, slug = pair.partition(":")
            if namespace == "effect" and slug:
                consumed_effects.add(slug)

    for row in db.query("SELECT src_trait_raw, tgt_trait_raw FROM relation"):
        for field in ("src_trait_raw", "tgt_trait_raw"):
            trait_ref = row.get(field)
            if not isinstance(trait_ref, str):
                continue
            namespace, _, slug = trait_ref.partition(":")
            if namespace == "effect" and slug:
                consumed_effects.add(slug)

    members_by_effect: dict[str, list[str]] = defaultdict(list)
    for row in db.query("SELECT id, name, effect FROM substance"):
        substance_label = f"{id_str(row['id'])} {cast(str, row['name'])}"
        for slug in cast("list[str]", row.get("effect") or []):
            if slug.endswith("_context"):
                members_by_effect[slug].append(substance_label)

    messages: list[str] = []
    for slug, members in sorted(members_by_effect.items()):
        if (
            slug in consumed_effects
            or len(members) < _CONTEXT_EFFECT_WITHOUT_CONSUMER_MIN_SUBSTANCES
        ):
            continue
        messages.append(
            f"effect:{slug} is assigned to {len(members)} substances but no "
            "dashboard or relation consumes it. "
            f"Members: {', '.join(sorted(members))}. "
            "Resolution: connect it to a review surface, demote it to notes, "
            "or delete it if another trait already carries the meaning."
        )
    return messages


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
