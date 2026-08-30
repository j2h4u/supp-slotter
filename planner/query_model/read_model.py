"""Public read-model facade used by planner commands."""

from __future__ import annotations

from planner.contracts import Product, Relation, Substance
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.policies import project_ontology_assertions
from planner.query_model.data import ReadModelContext, ReadModelData
from planner.query_model.facts import (
    active_fact_index,
    active_substance_ids,
    inactive_substance_ids,
)
from planner.query_model.projections import ontology_assertion_record
from planner.query_model.relation_conflicts import (
    RelationConflictWarningRow,
    collect_intra_product_scheduling_constraint_conflicts,
)
from planner.query_model.relation_matches import collect_substance_relation_matches
from planner.query_model.relation_warnings import (
    RelationWarningRow,
    collect_relation_warnings,
)
from planner.query_model.relations import (
    classify_relations,
)
from planner.schedule_types import ActiveFactIndexEntry
from planner.scheduling_constraint_execution import compile_scheduling_constraint_execution_plans


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

    def collect_relation_warnings(
        self,
        active_substances: set[str],
    ) -> list[RelationWarningRow]:
        return collect_relation_warnings(
            self._data.assertions, active_substances, self._ontology_bundle.runtime_program
        )

    def collect_intra_product_scheduling_constraint_conflicts(
        self,
        *,
        item_id: str,
        product_id: str,
        component_ids: list[str],
    ) -> list[RelationConflictWarningRow]:
        return collect_intra_product_scheduling_constraint_conflicts(
            self._data.scheduling_constraint_plans,
            self._ontology_bundle.runtime_program,
            item_id=item_id,
            product_id=product_id,
            component_ids=component_ids,
        )

    def substance_relation_matches(
        self,
        substance_id: str,
        substance_name: str,
    ) -> list[tuple[dict[str, object], list[str]]]:
        return collect_substance_relation_matches(self._data.assertions, substance_id, substance_name)

    def active_substance_ids(self) -> set[str]:
        return active_substance_ids(self._data, self._ontology_bundle.runtime_program.glue_contract.inactive_stack_name)

    def inactive_substance_ids(self) -> set[str]:
        return inactive_substance_ids(
            self._data, self._ontology_bundle.runtime_program.glue_contract.inactive_stack_name
        )

    def classify_relations(
        self,
        active_substances: set[str],
    ) -> dict[str, list[dict[str, object]]]:
        return classify_relations(self._data.assertions, active_substances, self._ontology_bundle.runtime_program)

    def active_fact_index(
        self,
        *,
        item_id_sequence: list[str],
        item_products: dict[str, str],
    ) -> list[ActiveFactIndexEntry]:
        return active_fact_index(
            self._data,
            self._ontology_bundle,
            item_id_sequence=item_id_sequence,
            item_products=item_products,
        )


def build_stack_read_model(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product] | None = None,
    *,
    context: ReadModelContext | None = None,
    ontology_bundle: OntologyBundle,
) -> StackReadModel:
    """Build the command-scoped read model from loaded YAML/domain objects."""
    loaded_context = context or ReadModelContext(None, None, None, None)
    assertions = project_ontology_assertions(relations, ontology_bundle)
    # Raw constraints are retained for provenance rows, while this
    # boundary is the canonical fallback for callers that do not already own a
    # command-level compilation.  A supplied typed tuple is reused verbatim so
    # the planner command's exactly-once compilation is not repeated here.
    scheduling_constraint_plans = loaded_context.scheduling_constraint_plans
    if loaded_context.scheduling_constraints and not scheduling_constraint_plans:
        scheduling_constraint_plans = compile_scheduling_constraint_execution_plans(
            loaded_context.scheduling_constraints,
            substances,
            ontology_bundle.runtime_program,
            ontology_bundle=ontology_bundle,
        )
    return StackReadModel(
        ReadModelData(
            substances=substances,
            products=products or {},
            stacks=loaded_context.stacks_data or {},
            assertions=tuple(
                ontology_assertion_record(assertion, substances, ontology_bundle) for assertion in assertions
            ),
            scheduling_constraint_plans=scheduling_constraint_plans,
        ),
        ontology_bundle,
    )
