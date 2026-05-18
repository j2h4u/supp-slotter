"""Membership and fact-index queries for the planner read model."""

from __future__ import annotations

from typing import Any, cast

from planner.query_model.session import SurrealSession, id_str


def _stack_partition_substance_ids(db: SurrealSession, *, inactive: bool) -> set[str]:
    """Substance IDs referenced by products in stacks matching the partition."""
    op = "==" if inactive else "!="
    target_product_ids: set[str] = set()
    for row in db.query(f"SELECT products FROM stack WHERE name {op} 'inactive'"):
        target_product_ids.update(row.get("products") or [])

    result: set[str] = set()
    for row in db.query("SELECT id, components FROM product"):
        if id_str(row["id"]) in target_product_ids:
            result.update(row.get("components") or [])
    return result


def active_substance_ids(db: SurrealSession) -> set[str]:
    """Substance IDs referenced by any product in a non-inactive stack."""
    return _stack_partition_substance_ids(db, inactive=False)


def inactive_substance_ids(db: SurrealSession) -> set[str]:
    """Substance IDs referenced by any product in the 'inactive' stack."""
    return _stack_partition_substance_ids(db, inactive=True)


_KNOWLEDGE_NAMESPACE_ORDER: tuple[str, ...] = ("risk", "pathway", "effect", "context")


def _title_from_slug(slug: str) -> str:
    return slug.replace("_", " ").title()


def active_fact_index(
    db: SurrealSession,
    *,
    item_id_sequence: list[str],
    item_products: dict[str, str],
) -> list[dict[str, Any]]:
    """Build an inverted index of active knowledge facts to products."""
    active_product_ids: set[str] = {
        item_products[item_id] for item_id in item_id_sequence
    }
    if not active_product_ids:
        return []

    products_by_id: dict[str, dict[str, Any]] = {}
    for row in db.query("SELECT id, display_name, components FROM product"):
        pid = id_str(row["id"])
        if pid in active_product_ids:
            products_by_id[pid] = row

    active_component_ids: set[str] = set()
    for row in products_by_id.values():
        active_component_ids.update(row.get("components") or [])

    substances_by_id: dict[str, dict[str, Any]] = {}
    if active_component_ids:
        for row in db.query(
            "SELECT id, risk, pathway, effect, context FROM substance"
        ):
            sid = id_str(row["id"])
            if sid in active_component_ids:
                substances_by_id[sid] = row

    facts: dict[tuple[str, str], dict[str, str]] = {}
    for product_id, product_row in products_by_id.items():
        product_name = cast(str, product_row["display_name"])
        components = cast("list[str]", product_row.get("components") or [])
        for component_id in components:
            substance_row = substances_by_id.get(component_id)
            if substance_row is None:
                continue
            for namespace in _KNOWLEDGE_NAMESPACE_ORDER:
                slugs = cast("list[str]", substance_row.get(namespace) or [])
                for slug in slugs:
                    facts.setdefault((namespace, slug), {})[product_id] = product_name

    trait_label_by_pair: dict[tuple[str, str], str] = {}
    for row in db.query(
        "SELECT namespace, short_name, label FROM trait "
        "WHERE namespace INSIDE $namespaces",
        {"namespaces": list(_KNOWLEDGE_NAMESPACE_ORDER)},
    ):
        trait_label_by_pair[
            (cast(str, row["namespace"]), cast(str, row["short_name"]))
        ] = cast(str, row["label"])

    dashboard_name_by_slug: dict[str, str] = {
        cast(str, row["slug"]): cast(str, row["name"])
        for row in db.query("SELECT slug, name FROM dashboard")
    }

    def fact_label(namespace: str, slug: str) -> str:
        label = trait_label_by_pair.get((namespace, slug))
        if label:
            return label
        if namespace == "context":
            return dashboard_name_by_slug.get(slug, _title_from_slug(slug))
        return _title_from_slug(slug)

    namespace_rank = {
        namespace: index
        for index, namespace in enumerate(_KNOWLEDGE_NAMESPACE_ORDER)
    }
    index: list[dict[str, Any]] = []
    for namespace, slug in sorted(
        facts,
        key=lambda key: (
            namespace_rank.get(key[0], len(namespace_rank)),
            fact_label(key[0], key[1]).casefold(),
            key[1],
        ),
    ):
        product_entries = sorted(
            facts[(namespace, slug)].values(), key=str.casefold
        )
        index.append(
            {
                "namespace": namespace,
                "fact": slug,
                "label": fact_label(namespace, slug),
                "product_count": len(product_entries),
                "products": product_entries,
            }
        )
    return index
