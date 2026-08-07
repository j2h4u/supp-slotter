"""Membership and fact-index queries for the planner read model."""

from __future__ import annotations

from typing import cast

from planner.ontology.artifacts import OntologyBundle
from planner.query_model.session import SurrealSession, id_str, string_list
from planner.schedule_types import ActiveFactIndexEntry


def _stack_partition_substance_ids(db: SurrealSession, *, inactive: bool, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by products in stacks matching the partition."""
    op = "==" if inactive else "!="
    target_product_ids: set[str] = set()
    for row in db.query(
        f"SELECT products FROM stack WHERE name {op} $inactive_stack_name", {"inactive_stack_name": inactive_stack_name}
    ):
        target_product_ids.update(string_list(row.get("products")))

    result: set[str] = set()
    for row in db.query("SELECT id, components FROM product"):
        if id_str(row["id"]) in target_product_ids:
            result.update(string_list(row.get("components")))
    return result


def active_substance_ids(db: SurrealSession, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by any product in a non-inactive stack."""
    return _stack_partition_substance_ids(db, inactive=False, inactive_stack_name=inactive_stack_name)


def inactive_substance_ids(db: SurrealSession, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by products in the authored inactive stack."""
    return _stack_partition_substance_ids(db, inactive=True, inactive_stack_name=inactive_stack_name)


def _title_from_slug(slug: str) -> str:
    return slug.replace("_", " ").title()


def _knowledge_namespaces(ontology_bundle: OntologyBundle) -> tuple[str, ...]:
    raw_presentation = ontology_bundle.runtime_vocabulary.get("schedule_presentation")
    if not isinstance(raw_presentation, dict):
        return ()
    presentation = cast(dict[str, object], raw_presentation)
    raw_active_fact_index = presentation.get("active_fact_index")
    if not isinstance(raw_active_fact_index, dict):
        return ()
    active_fact_index = cast(dict[str, object], raw_active_fact_index)
    include_namespaces = active_fact_index.get("include_namespaces")
    if not isinstance(include_namespaces, list):
        return ()
    return tuple(namespace for namespace in include_namespaces if isinstance(namespace, str))


def active_fact_index(
    db: SurrealSession,
    ontology_bundle: OntologyBundle,
    *,
    item_id_sequence: list[str],
    item_products: dict[str, str],
) -> list[ActiveFactIndexEntry]:
    """Build an inverted index of active knowledge facts to products."""
    active_product_ids: set[str] = {item_products[item_id] for item_id in item_id_sequence}
    if not active_product_ids:
        return []

    products_by_id = _active_products_by_id(db, active_product_ids)
    knowledge_namespaces = _knowledge_namespaces(ontology_bundle)
    substances_by_id = _active_substances_by_id(db, products_by_id)
    facts = _facts_by_namespace_slug(products_by_id, substances_by_id, knowledge_namespaces)
    labels = _FactLabels.from_db(db, ontology_bundle)

    namespace_rank = {namespace: index for index, namespace in enumerate(knowledge_namespaces)}
    index: list[ActiveFactIndexEntry] = []
    for namespace, slug in sorted(
        facts,
        key=lambda key: (
            namespace_rank.get(key[0], len(namespace_rank)),
            labels.label(key[0], key[1]).casefold(),
            key[1],
        ),
    ):
        product_entries = sorted(facts[(namespace, slug)].values(), key=str.casefold)
        index.append({
            "namespace": namespace,
            "fact": slug,
            "label": labels.label(namespace, slug),
            "product_count": len(product_entries),
            "products": product_entries,
        })
    return index


def _active_products_by_id(db: SurrealSession, active_product_ids: set[str]) -> dict[str, dict[str, object]]:
    products_by_id: dict[str, dict[str, object]] = {}
    for row in db.query("SELECT id, display_name, components FROM product"):
        product_id = id_str(row["id"])
        if product_id in active_product_ids:
            products_by_id[product_id] = row
    return products_by_id


def _active_substances_by_id(
    db: SurrealSession,
    products_by_id: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    active_component_ids: set[str] = set()
    for row in products_by_id.values():
        active_component_ids.update(string_list(row.get("components")))
    if not active_component_ids:
        return {}

    substances_by_id: dict[str, dict[str, object]] = {}
    for row in db.query("SELECT * FROM substance"):
        substance_id = id_str(row["id"])
        if substance_id in active_component_ids:
            substances_by_id[substance_id] = row
    return substances_by_id


def _facts_by_namespace_slug(
    products_by_id: dict[str, dict[str, object]],
    substances_by_id: dict[str, dict[str, object]],
    knowledge_namespaces: tuple[str, ...],
) -> dict[tuple[str, str], dict[str, str]]:
    facts: dict[tuple[str, str], dict[str, str]] = {}
    for product_id, product_row in products_by_id.items():
        product_name = cast(str, product_row["display_name"])
        for component_id in string_list(product_row.get("components")):
            _add_substance_facts(
                facts,
                product_id,
                product_name,
                substances_by_id.get(component_id),
                knowledge_namespaces,
            )
    return facts


def _add_substance_facts(
    facts: dict[tuple[str, str], dict[str, str]],
    product_id: str,
    product_name: str,
    substance_row: dict[str, object] | None,
    knowledge_namespaces: tuple[str, ...],
) -> None:
    if substance_row is None:
        return
    for namespace in knowledge_namespaces:
        slugs = cast("list[str]", substance_row.get(namespace) or [])
        for slug in slugs:
            facts.setdefault((namespace, slug), {})[product_id] = product_name


class _FactLabels:
    vocabulary_label_by_pair: dict[tuple[str, str], str]
    dashboard_name_by_slug: dict[str, str]

    def __init__(
        self,
        vocabulary_label_by_pair: dict[tuple[str, str], str],
        dashboard_name_by_slug: dict[str, str],
    ) -> None:
        self.vocabulary_label_by_pair = vocabulary_label_by_pair
        self.dashboard_name_by_slug = dashboard_name_by_slug

    @classmethod
    def from_db(cls, db: SurrealSession, ontology_bundle: OntologyBundle) -> _FactLabels:
        vocabulary = ontology_bundle.runtime_vocabulary
        vocabulary_label_by_pair: dict[tuple[str, str], str] = {}
        raw_terms = vocabulary.get("terms", [])
        if isinstance(raw_terms, list):
            for raw_term in raw_terms:
                if not isinstance(raw_term, dict):
                    continue
                term = cast(dict[str, object], raw_term)
                namespace, slug, label = term.get("semantic_category"), term.get("slug"), term.get("label")
                if all(isinstance(value, str) for value in (namespace, slug, label)):
                    vocabulary_label_by_pair[(cast(str, namespace), cast(str, slug))] = cast(str, label)

        dashboard_name_by_slug: dict[str, str] = {
            cast(str, row["slug"]): cast(str, row["name"]) for row in db.query("SELECT slug, name FROM dashboard")
        }
        return cls(vocabulary_label_by_pair, dashboard_name_by_slug)

    def label(self, namespace: str, slug: str) -> str:
        label = self.vocabulary_label_by_pair.get((namespace, slug))
        if label:
            return label
        if namespace == "context":
            return self.dashboard_name_by_slug.get(slug, _title_from_slug(slug))
        return _title_from_slug(slug)
