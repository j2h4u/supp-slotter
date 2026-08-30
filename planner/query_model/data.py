"""Command-scoped data used by the planner read-model facade."""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import Dashboard, OntologyAssertion, Product, SchedulingConstraint, SchedulingPolicy, Substance
from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan


@dataclass(frozen=True, slots=True)
class ReadModelContext:
    """Optional inputs needed by review and warning projections."""

    policies: dict[str, SchedulingPolicy] | None
    stacks_data: dict[str, list[str]] | None
    pillbox_stack_names: set[str] | None
    dashboards: dict[str, Dashboard] | None
    scheduling_constraints: tuple[SchedulingConstraint, ...] = ()
    scheduling_constraint_plans: tuple[SchedulingConstraintExecutionPlan, ...] = ()
    ontology_assertions: tuple[OntologyAssertion, ...] = ()


@dataclass(frozen=True, slots=True)
class ReadModelData:
    """Plain immutable command data; no database or query language involved."""

    substances: dict[str, Substance]
    products: dict[str, Product]
    stacks: dict[str, list[str]]
    assertions: tuple[dict[str, object], ...]
    scheduling_constraint_plans: tuple[SchedulingConstraintExecutionPlan, ...]
