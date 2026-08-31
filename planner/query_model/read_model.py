"""Public read-model facade used by planner commands."""

from __future__ import annotations

from planner.contracts import Product, Relation, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.policies import project_ontology_assertions
from planner.query_model.data import ReadModelData
from planner.query_model.facts import active_substance_ids
from planner.query_model.relations import classify_relations, resolve_relation_queries
from planner.query_model.types import RelationReviewRow


class StackReadModel:
    """Facade over plain command-scoped domain data."""

    _data: ReadModelData
    _ontology_bundle: OntologyBundle

    def __init__(self, data: ReadModelData, ontology_bundle: OntologyBundle) -> None:
        self._data = data
        self._ontology_bundle = ontology_bundle

    @property
    def ontology_bundle(self) -> OntologyBundle:
        """The verified ontology bundle used to build this command read model."""
        return self._ontology_bundle

    def active_substance_ids(self) -> set[str]:
        routable_stack_names = set(
            self._ontology_bundle.runtime_program.glue_contract.stack_partition.routable_stack_names
        )
        return active_substance_ids(self._data, routable_stack_names)

    def classify_relations(
        self,
        active_substances: set[str],
    ) -> list[RelationReviewRow]:
        return classify_relations(self._data.relations, active_substances, self._ontology_bundle.runtime_program)


def build_stack_read_model(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product],
    stacks: dict[str, list[str]],
    *,
    ontology_bundle: OntologyBundle,
) -> StackReadModel:
    """Build the command-scoped read model from loaded YAML/domain objects."""
    _validate_catalog_references(substances, products, stacks)
    assertions = project_ontology_assertions(relations, ontology_bundle)
    return StackReadModel(
        ReadModelData(
            substances=substances,
            products=products,
            stacks=stacks,
            relations=resolve_relation_queries(assertions, substances, ontology_bundle),
        ),
        ontology_bundle,
    )


def _validate_catalog_references(
    substances: dict[str, Substance],
    products: dict[str, Product],
    stacks: dict[str, list[str]],
) -> None:
    """Reject dangling stack and composition references before query projection."""
    for stack_name, product_ids in stacks.items():
        if not stack_name:
            raise ValueError("read-model stack name must be non-empty")
        for index, product_id in enumerate(product_ids):
            if product_id not in products:
                raise ValueError(f"read-model stack {stack_name!r}[{index}] references missing product {product_id!r}")

    for product_id, product in products.items():
        for index, component in enumerate(product.components):
            if component.substance not in substances:
                raise ValueError(
                    f"read-model product {product_id!r}.components[{index}] "
                    f"references missing substance {component.substance!r}"
                )
