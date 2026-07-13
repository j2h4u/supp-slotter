"""Audit queries for the SurrealDB-backed planner read model.

Set-difference arithmetic stays in Python where it is clearer. SurrealQL owns
the cross-reference collection across heterogeneous sources: product
components, resolved relation endpoints, substance prefer_with arrays, and
dashboard selectors resolution.

`similar_names` stays in Python because it depends on SequenceMatcher fuzzy
matching, which has no native SurrealQL equivalent.
"""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from planner.cards.substance import format_substance_name
from planner.cards.substance_similarity import collect_similar_substances
from planner.contracts import Substance
from planner.ontology.artifacts import load_runtime_vocabulary
from planner.paths import ROOT
from planner.query_model.session import SurrealSession, id_str, string_list

_SCHEDULING_NAMESPACES = frozenset({"intake", "timing", "activity"})
_EFFECT_USAGE_REVIEW_MIN_SUBSTANCES = 3
_CONTEXT_EFFECT_WITHOUT_CONSUMER_MIN_SUBSTANCES = 3
_RELATION_TRAIT_ENDPOINT_MEMBER_LIMIT = 5
_ALLOWED_BROAD_RELATION_TRAIT_ENDPOINTS = frozenset({
    ("review_with", "effect:incretin_drug_context", "is:fiber"),
    ("review_with", "effect:incretin_drug_context", "Metformin"),
    ("review_with", "effect:incretin_drug_context", "risk:glucose_med_interaction"),
    ("supports", "Creatine", "effect:incretin_drug_context"),
    ("supports", "Whey protein", "effect:incretin_drug_context"),
})
MIN_OVERLAP_REVIEW_SLUGS = 2


def collect_cleanup_sections(
    db: SurrealSession,
    substances: dict[str, Substance],
) -> dict[str, list[str]]:
    """Return cleanup-candidate sections for `planner audit`."""
    all_substance_ids = {id_str(row["id"]) for row in db.query("SELECT id FROM substance")}
    product_substance_refs, prefer_with_refs, relation_refs = _referenced_substance_ids(db)

    knowledge_only_substances = [
        _format_substance_audit_entry(substances[substance_id])
        for substance_id in sorted(all_substance_ids - product_substance_refs - prefer_with_refs - relation_refs)
        if substance_id in substances
    ]

    all_product_ids = {id_str(row["id"]) for row in db.query("SELECT id FROM product")}
    stack_products: set[str] = set()
    for row in db.query("SELECT products FROM stack"):
        stack_products.update(string_list(row.get("products")))
    products_without_stack = _products_without_stack_messages(db, all_product_ids - stack_products)

    empty_stacks, stacks_without_pillboxes, pillboxes_without_stack = _stack_cleanup_sections(db)
    similar_names = collect_similar_substances(substances)

    return {
        "substances.knowledge_only": knowledge_only_substances,
        "products.without_stack": products_without_stack,
        "ontology.policies.unused": _unused_scheduling_policies(db),
        "context.without_dashboard_selector": _collect_context_without_dashboard_selector_messages(db),
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": similar_names,
        "dashboard.empty_cluster": _empty_dashboard_cluster_messages(db),
        "effects.context_without_consumer": _collect_context_effect_without_consumer_messages(db),
        "effects.overlap_review": _collect_effect_overlap_messages(db),
        "relations.broad_trait_endpoint": _collect_broad_relation_trait_endpoint_messages(db),
    }


def _referenced_substance_ids(db: SurrealSession) -> tuple[set[str], set[str], set[str]]:
    product_substance_refs: set[str] = set()
    for row in db.query("SELECT components FROM product"):
        product_substance_refs.update(string_list(row.get("components")))

    prefer_with_refs: set[str] = set()
    for row in db.query("SELECT id, prefer_with FROM substance WHERE array::len(prefer_with) > 0"):
        prefer_with_refs.add(id_str(row["id"]))
        prefer_with_refs.update(string_list(row.get("prefer_with")))

    relation_refs: set[str] = set()
    for row in db.query("SELECT src_substances, tgt_substances FROM relation"):
        relation_refs.update(string_list(row.get("src_substances")))
        relation_refs.update(string_list(row.get("tgt_substances")))

    return product_substance_refs, prefer_with_refs, relation_refs


def _unused_scheduling_policies(db: SurrealSession) -> list[str]:
    """Report canonical scheduling policies with no card assignment."""
    vocabulary = load_runtime_vocabulary(ROOT / "ontology")
    policies = vocabulary.get("scheduling_policies")
    if not isinstance(policies, dict):
        return []
    assigned: set[str] = set()
    for row in db.query("SELECT term_refs FROM substance"):
        assigned.update(string_list(row.get("term_refs")))
    for row in db.query("SELECT intake, timing, activity FROM substance"):
        for category in ("intake", "timing", "activity"):
            assigned.update(f"{category}:{term}" for term in string_list(row.get(category)))
    return sorted(policy_id for policy_id in policies if isinstance(policy_id, str) and policy_id not in assigned)


def _products_without_stack_messages(db: SurrealSession, product_ids: set[str]) -> list[str]:
    rows_by_id = {
        id_str(row["id"]): cast(str, row.get("display_name") or row["id"])
        for row in db.query("SELECT id, display_name FROM product")
    }
    return [f"{rows_by_id.get(product_id, product_id)} ({product_id})" for product_id in sorted(product_ids)]


def _stack_cleanup_sections(db: SurrealSession) -> tuple[list[str], list[str], list[str]]:
    empty_stacks = sorted(
        cast(str, row["name"]) for row in db.query("SELECT name FROM stack WHERE array::len(products) == 0")
    )
    all_stack_names: set[str] = {cast(str, row["name"]) for row in db.query("SELECT name FROM stack")}
    pillbox_stack_names: set[str] = {cast(str, row["stack_name"]) for row in db.query("SELECT stack_name FROM pillbox")}
    stacks_without_pillboxes = sorted(all_stack_names - pillbox_stack_names - {"inactive"})
    pillboxes_without_stack = sorted(pillbox_stack_names - all_stack_names)
    return empty_stacks, stacks_without_pillboxes, pillboxes_without_stack


def _empty_dashboard_cluster_messages(db: SurrealSession) -> list[str]:
    messages: list[str] = []
    for dash in db.query("SELECT slug, from_terms FROM dashboard"):
        slug = cast(str, dash["slug"])
        pairs = cast("list[str]", dash.get("from_terms") or [])
        if pairs:
            members = db.query(
                "SELECT id FROM substance WHERE term_refs ANYINSIDE $pairs",
                {"pairs": pairs},
            )
            if members:
                continue
        messages.append(
            f"Empty cluster: data/dashboards/{slug}.yaml selectors resolves to "
            f"zero member substances (using union resolution: OR across all listed "
            f"(namespace, slug) pairs). Resolution: update selectors to match "
            f"substance ontology terms, OR remove the dashboard yaml if abandoned."
        )
    return messages


def _collect_context_without_dashboard_selector_messages(
    db: SurrealSession,
) -> list[str]:
    """Return context tags that no dashboard consumes."""
    selected_contexts: set[str] = set()
    for row in db.query("SELECT from_terms FROM dashboard"):
        for pair in cast("list[str]", row.get("from_terms") or []):
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
            "dashboard selectors selector consumes it. "
            f"Members: {', '.join(sorted(members))}. "
            "Resolution: remove stale context tags, add a dashboard selector, "
            "or document an explicit exception."
        )
    return messages


def _collect_context_effect_without_consumer_messages(
    db: SurrealSession,
) -> list[str]:
    """Return high-use effect:*_context slugs that no dashboard or relation consumes."""
    consumed_effects = _consumed_effect_slugs(db)
    members_by_effect = _context_effect_members(db)

    messages: list[str] = []
    for slug, members in sorted(members_by_effect.items()):
        if slug in consumed_effects or len(members) < _CONTEXT_EFFECT_WITHOUT_CONSUMER_MIN_SUBSTANCES:
            continue
        messages.append(
            f"effect:{slug} is assigned to {len(members)} substances but no "
            "dashboard or relation consumes it. "
            f"Members: {', '.join(sorted(members))}. "
            "Resolution: connect it to a review surface, demote it to notes, "
            "or delete it if another trait already carries the meaning."
        )
    return messages


def _consumed_effect_slugs(db: SurrealSession) -> set[str]:
    consumed_effects: set[str] = set()
    for row in db.query("SELECT from_terms FROM dashboard"):
        for pair in cast("list[str]", row.get("from_terms") or []):
            namespace, _, slug = pair.partition(":")
            if namespace == "effect" and slug:
                consumed_effects.add(slug)

    for row in db.query("SELECT src_selector, tgt_selector FROM relation"):
        for field in ("src_selector", "tgt_selector"):
            selector = row.get(field)
            selector_mapping = cast(dict[str, object], selector) if isinstance(selector, dict) else None
            if selector_mapping is not None and selector_mapping.get("category") == "effect":
                term = selector_mapping.get("term")
                if isinstance(term, str):
                    consumed_effects.add(term)
    return consumed_effects


def _context_effect_members(db: SurrealSession) -> dict[str, list[str]]:
    members_by_effect: dict[str, list[str]] = defaultdict(list)
    for row in db.query("SELECT id, name, effect FROM substance"):
        substance_label = f"{id_str(row['id'])} {cast(str, row['name'])}"
        for slug in cast("list[str]", row.get("effect") or []):
            if slug.endswith("_context"):
                members_by_effect[slug].append(substance_label)
    return members_by_effect


def _collect_effect_overlap_messages(db: SurrealSession) -> list[str]:
    """Return non-blocking review hints for potentially overlapping effect axes."""
    effect_labels: dict[str, str] = {}
    for row in db.query("SELECT effect FROM substance"):
        for slug in string_list(row.get("effect")):
            effect_labels.setdefault(slug, slug.replace("_", " "))

    messages: list[str] = []
    messages.extend(_same_stem_effect_messages(effect_labels))
    messages.extend(_same_usage_effect_messages(db, effect_labels))
    return messages


def _collect_broad_relation_trait_endpoint_messages(db: SurrealSession) -> list[str]:
    """Return trait-endpoint relations that may over-broadly inherit future cards."""
    messages: list[str] = []
    for row in db.query(
        "SELECT type, src_key, tgt_key, src_selector, tgt_selector, src_substances, tgt_substances FROM relation"
    ):
        relation_type = cast(str, row["type"])
        source_key = cast(str, row["src_key"])
        target_key = cast(str, row["tgt_key"])
        if (relation_type, source_key, target_key) in _ALLOWED_BROAD_RELATION_TRAIT_ENDPOINTS:
            continue

        endpoint_messages = _broad_trait_endpoint_parts(row)
        messages.extend(f"{relation_type} {source_key} -> {target_key}: {message}" for message in endpoint_messages)
    return sorted(messages)


def _broad_trait_endpoint_parts(row: dict[str, object]) -> list[str]:
    endpoint_parts: list[str] = []
    source_key = cast(str, row["src_key"])
    target_key = cast(str, row["tgt_key"])
    source_selector = row.get("src_selector")
    target_selector = row.get("tgt_selector")
    source_mapping = cast(dict[str, object], source_selector) if isinstance(source_selector, dict) else {}
    target_mapping = cast(dict[str, object], target_selector) if isinstance(target_selector, dict) else {}
    source_kind = "term" if source_mapping.get("kind") == "term" else "entity"
    target_kind = "term" if target_mapping.get("kind") == "term" else "entity"
    source_size = len(string_list(row.get("src_substances")))
    target_size = len(string_list(row.get("tgt_substances")))
    if source_kind == "term" and source_size > _RELATION_TRAIT_ENDPOINT_MEMBER_LIMIT:
        endpoint_parts.append(_broad_trait_endpoint_message("source", source_key, source_size))
    if target_kind == "term" and target_size > _RELATION_TRAIT_ENDPOINT_MEMBER_LIMIT:
        endpoint_parts.append(_broad_trait_endpoint_message("target", target_key, target_size))
    return endpoint_parts


def _broad_trait_endpoint_message(side: str, key: str, size: int) -> str:
    return (
        f"{side} trait endpoint {key} resolves to {size} substances. "
        "Resolution: narrow the trait, use concrete substance/name endpoints, "
        "or add an explicit audit allowlist entry with rationale if inheritance "
        "by future cards is intentional."
    )


def _same_stem_effect_messages(effect_labels: dict[str, str]) -> list[str]:
    by_stem: dict[str, list[str]] = defaultdict(list)
    for slug in effect_labels:
        by_stem[_effect_overlap_stem(slug)].append(slug)

    messages: list[str] = []
    for _stem, slugs in sorted(by_stem.items()):
        if len(slugs) < MIN_OVERLAP_REVIEW_SLUGS:
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
        if len(slugs) < MIN_OVERLAP_REVIEW_SLUGS or len(substance_ids) < _EFFECT_USAGE_REVIEW_MIN_SUBSTANCES:
            continue
        substance_names = [f"{substance_id} {names_by_id[substance_id]}" for substance_id in substance_ids]
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
