"""Public read-model facade used by planner commands."""

from __future__ import annotations

from planner.contracts import OntologyAssertion, Product, Relation, Substance
from planner.ontology.policies import project_ontology_assertions
from planner.query_model.audit import collect_cleanup_sections
from planner.query_model.audit_full import collect_full_audit_sections
from planner.query_model.facts import (
    active_fact_index,
    active_substance_ids,
    inactive_substance_ids,
)
from planner.query_model.relation_conflicts import (
    RelationConflictWarningRow,
    collect_intra_product_scheduling_constraint_conflicts,
)
from planner.query_model.relation_matches import collect_substance_relation_matches
from planner.query_model.relation_warnings import (
    RelationWarningRow,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    collect_review_with_relations,
)
from planner.query_model.relations import (
    classify_relations,
)
from planner.query_model.session import SurrealSession
from planner.query_model.surreal import SurrealLoadContext, build_surreal_session
from planner.schedule_types import ActiveFactIndexEntry


class StackReadModel:
    """Facade over the command-scoped SurrealDB read model.

    Commands and scheduling code depend on this surface, not on the SurrealDB SDK
    or raw SurrealQL.
    """

    _db: SurrealSession

    def __init__(self, db: SurrealSession) -> None:
        self._db = db

    def collect_review_with_relations(
        self,
        active_substances: set[str],
    ) -> list[RelationWarningRow]:
        return collect_review_with_relations(self._db, active_substances)

    def collect_missing_balance_relations(
        self,
        active_substances: set[str],
    ) -> list[RelationWarningRow]:
        return collect_missing_balance_relations(self._db, active_substances)

    def collect_missing_support_relations(
        self,
        active_substances: set[str],
    ) -> list[RelationWarningRow]:
        return collect_missing_support_relations(self._db, active_substances)

    def collect_intra_product_scheduling_constraint_conflicts(
        self,
        *,
        item_id: str,
        product_id: str,
        component_ids: list[str],
    ) -> list[RelationConflictWarningRow]:
        return collect_intra_product_scheduling_constraint_conflicts(
            self._db,
            item_id=item_id,
            product_id=product_id,
            component_ids=component_ids,
        )

    def substance_relation_matches(
        self,
        substance_id: str,
        substance_name: str,
    ) -> list[tuple[dict[str, object], list[str]]]:
        return collect_substance_relation_matches(self._db, substance_id, substance_name)

    def active_substance_ids(self) -> set[str]:
        return active_substance_ids(self._db)

    def inactive_substance_ids(self) -> set[str]:
        return inactive_substance_ids(self._db)

    def classify_relations(
        self,
        active_substances: set[str],
    ) -> dict[str, list[dict[str, object]]]:
        return classify_relations(self._db, active_substances)

    def active_fact_index(
        self,
        *,
        item_id_sequence: list[str],
        item_products: dict[str, str],
    ) -> list[ActiveFactIndexEntry]:
        return active_fact_index(
            self._db,
            item_id_sequence=item_id_sequence,
            item_products=item_products,
        )

    def cleanup_sections(
        self,
        substances: dict[str, Substance],
    ) -> dict[str, list[str]]:
        return collect_cleanup_sections(self._db, substances)

    def full_audit_sections(
        self,
        substances: dict[str, Substance],
        products: dict[str, Product],
    ) -> dict[str, list[str]]:
        return collect_full_audit_sections(self._db, substances, products)


def build_stack_read_model(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product] | None = None,
    *,
    context: SurrealLoadContext | None = None,
    ontology_assertions: tuple[OntologyAssertion, ...] | None = None,
) -> StackReadModel:
    """Build the command-scoped read model from loaded YAML/domain objects."""
    loaded_context = context or SurrealLoadContext(None, None, None, None)
    assertions = project_ontology_assertions(relations) if ontology_assertions is None else ontology_assertions
    loaded_context = SurrealLoadContext(
        policies=loaded_context.policies,
        stacks_data=loaded_context.stacks_data,
        pillbox_stack_names=loaded_context.pillbox_stack_names,
        dashboards=loaded_context.dashboards,
        scheduling_constraints=loaded_context.scheduling_constraints,
        ontology_assertions=assertions,
    )
    return StackReadModel(
        build_surreal_session(
            substances,
            relations,
            products,
            loaded_context,
        )
    )
