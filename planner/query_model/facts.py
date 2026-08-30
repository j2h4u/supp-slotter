"""Membership and fact-index queries for the planner read model."""

from __future__ import annotations

from planner.cards.product import format_product_name
from planner.contracts import Product, Substance
from planner.ontology.artifacts import OntologyBundle, _is_verified_bundle
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.presentation import load_term_labels
from planner.query_model.data import ReadModelData
from planner.schedule_types import ActiveFactIndexEntry


def _stack_partition_substance_ids(data: ReadModelData, *, inactive: bool, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by products in stacks matching the partition."""
    target_product_ids: set[str] = set()
    for name, product_ids in data.stacks.items():
        if (name == inactive_stack_name) is inactive:
            target_product_ids.update(product_ids)

    result: set[str] = set()
    for product_id in target_product_ids:
        product = data.products[product_id]
        result.update(component.substance for component in product.components)
    return result


def active_substance_ids(data: ReadModelData, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by any product in a non-inactive stack."""
    return _stack_partition_substance_ids(data, inactive=False, inactive_stack_name=inactive_stack_name)


def inactive_substance_ids(data: ReadModelData, inactive_stack_name: str) -> set[str]:
    """Substance IDs referenced by products in the authored inactive stack."""
    return _stack_partition_substance_ids(data, inactive=True, inactive_stack_name=inactive_stack_name)


def active_fact_index(
    data: ReadModelData,
    ontology_bundle: OntologyBundle,
    *,
    item_id_sequence: list[str],
    item_products: dict[str, str],
) -> list[ActiveFactIndexEntry]:
    """Build an inverted index of active knowledge facts to products."""
    missing_item_ids = [item_id for item_id in item_id_sequence if item_id not in item_products]
    if missing_item_ids:
        raise ValueError(f"active fact index has no product mapping for item {missing_item_ids[0]!r}")
    active_product_ids: set[str] = {item_products[item_id] for item_id in item_id_sequence}
    if not active_product_ids:
        return []

    missing_product_ids = sorted(active_product_ids - data.products.keys())
    if missing_product_ids:
        raise ValueError(f"active fact index references missing product {missing_product_ids[0]!r}")
    products_by_id = {product_id: data.products[product_id] for product_id in active_product_ids}
    substances_by_id = _active_substances_by_id(data.substances, products_by_id)
    knowledge_namespaces = tuple(
        sorted({
            assertion.category
            for substance in substances_by_id.values()
            for assertion in substance.knowledge_assertions
        })
    )
    facts = _facts_by_namespace_slug(products_by_id, substances_by_id, knowledge_namespaces)
    labels = _FactLabels.from_bundle(ontology_bundle)

    namespace_rank = {namespace: index for index, namespace in enumerate(knowledge_namespaces)}
    index: list[ActiveFactIndexEntry] = []
    for namespace, slug in sorted(
        facts,
        key=lambda key: (
            namespace_rank[key[0]],
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


def _active_substances_by_id(
    substances: dict[str, Substance],
    products_by_id: dict[str, Product],
) -> dict[str, Substance]:
    active_component_ids: set[str] = set()
    for product in products_by_id.values():
        active_component_ids.update(component.substance for component in product.components)
    if not active_component_ids:
        return {}

    return {substance_id: substances[substance_id] for substance_id in active_component_ids}


def _facts_by_namespace_slug(
    products_by_id: dict[str, Product],
    substances_by_id: dict[str, Substance],
    knowledge_namespaces: tuple[str, ...],
) -> dict[tuple[str, str], dict[str, str]]:
    facts: dict[tuple[str, str], dict[str, str]] = {}
    for product_id, product in products_by_id.items():
        product_name = format_product_name(product)
        for component in product.components:
            _add_substance_facts(
                facts,
                product_id,
                product_name,
                substances_by_id[component.substance],
                knowledge_namespaces,
            )
    return facts


def _add_substance_facts(
    facts: dict[tuple[str, str], dict[str, str]],
    product_id: str,
    product_name: str,
    substance: Substance,
    knowledge_namespaces: tuple[str, ...],
) -> None:
    for assertion in substance.knowledge_assertions:
        namespace = assertion.category
        slug = assertion.value
        if namespace in knowledge_namespaces:
            facts.setdefault((namespace, slug), {})[product_id] = product_name


class _FactLabels:
    vocabulary_label_by_pair: dict[tuple[str, str], str]

    def __init__(
        self,
        vocabulary_label_by_pair: dict[tuple[str, str], str],
    ) -> None:
        self.vocabulary_label_by_pair = vocabulary_label_by_pair

    @classmethod
    def from_bundle(cls, ontology_bundle: OntologyBundle) -> _FactLabels:
        if not _is_verified_bundle(ontology_bundle):
            raise OntologyInfrastructureError(
                "Active fact labels require a verified OntologyBundle",
                code=MALFORMED,
            )
        return cls(dict(load_term_labels(ontology_bundle)))

    def label(self, namespace: str, slug: str) -> str:
        label = self.vocabulary_label_by_pair.get((namespace, slug))
        if label:
            return label
        raise OntologyInfrastructureError(f"ontology fact has no authored label for {namespace}:{slug}", code=MALFORMED)
