"""SurrealDB session construction for the planner read model.

YAML cards and dataclasses remain the source of truth. This module owns the
SurrealDB SDK construction and command-scoped in-memory database population.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from surrealdb import Surreal

from planner.contracts import (
    Dashboard,
    OntologyAssertion,
    Product,
    Relation,
    SchedulingConstraint,
    SchedulingPolicy,
    Substance,
)
from planner.query_model.session import SurrealSession
from planner.query_model.surreal_records import (
    dashboard_record,
    ontology_assertion_record,
    product_record,
    scheduling_constraint_execution_plan_record,
    scheduling_constraint_record,
    substance_record,
)
from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan


@dataclass(frozen=True, slots=True)
class SurrealLoadContext:
    policies: dict[str, SchedulingPolicy] | None
    stacks_data: dict[str, list[str]] | None
    pillbox_stack_names: set[str] | None
    dashboards: dict[str, Dashboard] | None
    scheduling_constraints: tuple[SchedulingConstraint, ...] = ()
    scheduling_constraint_plans: tuple[SchedulingConstraintExecutionPlan, ...] = ()
    ontology_assertions: tuple[OntologyAssertion, ...] = ()


def build_surreal_session(
    substances: dict[str, Substance],
    relations: list[Relation],
    products: dict[str, Product] | None = None,
    load_context: SurrealLoadContext | None = None,
) -> SurrealSession:
    """Load domain objects into an in-memory SurrealDB session."""
    context = load_context or SurrealLoadContext(
        policies=None,
        stacks_data=None,
        pillbox_stack_names=None,
        dashboards=None,
        scheduling_constraints=(),
        scheduling_constraint_plans=(),
        ontology_assertions=(),
    )
    db = cast(SurrealSession, Surreal("mem://"))
    db.use("planner", "read_model")

    _load_substances(db, substances)
    _load_ontology_assertions(db, context.ontology_assertions, substances)
    _load_scheduling_constraints(db, context.scheduling_constraints, substances)
    _load_scheduling_constraint_plans(db, context.scheduling_constraint_plans)
    _load_products(db, products)
    _load_stacks(db, context.stacks_data)
    _load_pillboxes(db, context.pillbox_stack_names)
    _load_dashboards(db, context.dashboards)
    return db


def _load_substances(db: SurrealSession, substances: dict[str, Substance]) -> None:
    for substance_id, substance in substances.items():
        db.create("substance", substance_record(substance_id, substance))


def _load_ontology_assertions(
    db: SurrealSession,
    assertions: tuple[OntologyAssertion, ...],
    substances: dict[str, Substance],
) -> None:
    for assertion in assertions:
        db.create("ontology_assertion", ontology_assertion_record(assertion, substances))


def _load_scheduling_constraints(
    db: SurrealSession,
    constraints: tuple[SchedulingConstraint, ...],
    substances: dict[str, Substance],
) -> None:
    for constraint in constraints:
        db.create("scheduling_constraint", scheduling_constraint_record(constraint, substances))


def _load_scheduling_constraint_plans(
    db: SurrealSession,
    plans: tuple[SchedulingConstraintExecutionPlan, ...],
) -> None:
    for plan in plans:
        db.create("scheduling_constraint_execution_plan", scheduling_constraint_execution_plan_record(plan))


def _load_products(db: SurrealSession, products: dict[str, Product] | None) -> None:
    if not products:
        return
    for product_id, product in products.items():
        db.create("product", product_record(product_id, product))


def _load_stacks(db: SurrealSession, stacks_data: dict[str, list[str]] | None) -> None:
    if not stacks_data:
        return
    for stack_name, product_ids in stacks_data.items():
        db.create("stack", {"name": stack_name, "products": list(product_ids)})


def _load_pillboxes(db: SurrealSession, pillbox_stack_names: set[str] | None) -> None:
    if not pillbox_stack_names:
        return
    for stack_name in pillbox_stack_names:
        db.create("pillbox", {"stack_name": stack_name})


def _load_dashboards(db: SurrealSession, dashboards: dict[str, Dashboard] | None) -> None:
    if not dashboards:
        return
    for slug, dashboard in dashboards.items():
        db.create("dashboard", dashboard_record(slug, dashboard))
