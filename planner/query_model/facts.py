"""Membership and fact-index queries for the planner read model."""

from __future__ import annotations

from typing import Any, cast

from planner.query_model.session import SurrealSession, id_str, string_list


def _stack_partition_substance_ids(db: SurrealSession, *, inactive: bool) -> set[str]:
    """Substance IDs referenced by products in stacks matching the partition."""
    op = "==" if inactive else "!="
    target_product_ids: set[str] = set()
    for row in db.query(f"SELECT products FROM stack WHERE name {op} 'inactive'"):
        target_product_ids.update(string_list(row.get("products")))

    result: set[str] = set()
    for row in db.query("SELECT id, components FROM product"):
        if id_str(row["id"]) in target_product_ids:
            result.update(string_list(row.get("components")))
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
    active_product_ids: set[str] = {item_products[item_id] for item_id in item_id_sequence}
    if not active_product_ids:
        return []

    products_by_id = _active_products_by_id(db, active_product_ids)
    substances_by_id = _active_substances_by_id(db, products_by_id)
    facts = _facts_by_namespace_slug(products_by_id, substances_by_id)
    labels = _FactLabels.from_db(db)

    namespace_rank = {namespace: index for index, namespace in enumerate(_KNOWLEDGE_NAMESPACE_ORDER)}
    index: list[dict[str, Any]] = []
    for namespace, slug in sorted(
        facts,
        key=lambda key: (
            namespace_rank.get(key[0], len(namespace_rank)),
            labels.label(key[0], key[1]).casefold(),
            key[1],
        ),
    ):
        product_entries = sorted(facts[(namespace, slug)].values(), key=str.casefold)
        index.append(
            {
                "namespace": namespace,
                "fact": slug,
                "label": labels.label(namespace, slug),
                "product_count": len(product_entries),
                "products": product_entries,
            }
        )
    return index


def _active_products_by_id(db: SurrealSession, active_product_ids: set[str]) -> dict[str, dict[str, Any]]:
    products_by_id: dict[str, dict[str, Any]] = {}
    for row in db.query("SELECT id, display_name, components FROM product"):
        product_id = id_str(row["id"])
        if product_id in active_product_ids:
            products_by_id[product_id] = row
    return products_by_id


def _active_substances_by_id(
    db: SurrealSession,
    products_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    active_component_ids: set[str] = set()
    for row in products_by_id.values():
        active_component_ids.update(string_list(row.get("components")))
    if not active_component_ids:
        return {}

    substances_by_id: dict[str, dict[str, Any]] = {}
    for row in db.query("SELECT id, risk, pathway, effect, context FROM substance"):
        substance_id = id_str(row["id"])
        if substance_id in active_component_ids:
            substances_by_id[substance_id] = row
    return substances_by_id


def _facts_by_namespace_slug(
    products_by_id: dict[str, dict[str, Any]],
    substances_by_id: dict[str, dict[str, Any]],
) -> dict[tuple[str, str], dict[str, str]]:
    facts: dict[tuple[str, str], dict[str, str]] = {}
    for product_id, product_row in products_by_id.items():
        product_name = cast(str, product_row["display_name"])
        for component_id in string_list(product_row.get("components")):
            _add_substance_facts(facts, product_id, product_name, substances_by_id.get(component_id))
    return facts


def _add_substance_facts(
    facts: dict[tuple[str, str], dict[str, str]],
    product_id: str,
    product_name: str,
    substance_row: dict[str, Any] | None,
) -> None:
    if substance_row is None:
        return
    for namespace in _KNOWLEDGE_NAMESPACE_ORDER:
        slugs = cast("list[str]", substance_row.get(namespace) or [])
        for slug in slugs:
            facts.setdefault((namespace, slug), {})[product_id] = product_name


class _FactLabels:
    def __init__(
        self,
        trait_label_by_pair: dict[tuple[str, str], str],
        dashboard_name_by_slug: dict[str, str],
    ) -> None:
        self.trait_label_by_pair = trait_label_by_pair
        self.dashboard_name_by_slug = dashboard_name_by_slug

    @classmethod
    def from_db(cls, db: SurrealSession) -> _FactLabels:
        trait_label_by_pair: dict[tuple[str, str], str] = {}
        for row in db.query(
            "SELECT namespace, short_name, label FROM trait WHERE namespace INSIDE $namespaces",
            {"namespaces": list(_KNOWLEDGE_NAMESPACE_ORDER)},
        ):
            trait_label_by_pair[(cast(str, row["namespace"]), cast(str, row["short_name"]))] = cast(str, row["label"])

        dashboard_name_by_slug: dict[str, str] = {
            cast(str, row["slug"]): cast(str, row["name"]) for row in db.query("SELECT slug, name FROM dashboard")
        }
        return cls(trait_label_by_pair, dashboard_name_by_slug)

    def label(self, namespace: str, slug: str) -> str:
        label = self.trait_label_by_pair.get((namespace, slug))
        if label:
            return label
        if namespace == "context":
            return self.dashboard_name_by_slug.get(slug, _title_from_slug(slug))
        return _title_from_slug(slug)
