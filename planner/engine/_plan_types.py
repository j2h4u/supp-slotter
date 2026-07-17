"""Shared plan-command data containers."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from planner.contracts import (
    GovernedScheduleProjection,
    Pillbox,
    Product,
    Relation,
    SchedulingConstraint,
    SchedulingPolicy,
    Slot,
    StackEntry,
    Substance,
)
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.runtime_program import RuntimeEffectScoring, RuntimeProgram
from planner.query_model.relation_conflicts import RelationConflictWarningRow
from planner.scheduling_constraint_execution import SchedulingConstraintExecutionPlan


class PlanInputs(NamedTuple):
    ontology_bundle: OntologyBundle
    runtime_program: RuntimeProgram
    effect_scoring: RuntimeEffectScoring
    slots: dict[str, Slot]
    policies: dict[str, SchedulingPolicy]
    scheduling_constraints: tuple[SchedulingConstraint, ...]
    substances: dict[str, Substance]
    products: dict[str, Product]
    global_relations: list[Relation]
    dashboard_files: list[Path]
    stack_entries: dict[str, StackEntry]
    pillboxes: dict[str, Pillbox]
    scheduling_constraint_plans: tuple[SchedulingConstraintExecutionPlan, ...] = ()


class ActiveIndex(NamedTuple):
    item_products: dict[str, str]
    active_components: dict[str, list[str]]
    intra_product_relation_conflicts_by_item: dict[str, list[RelationConflictWarningRow]]
    item_stacks: dict[str, str]
    governed_projection_by_item: dict[str, GovernedScheduleProjection]
    active_policy_ids_by_item: dict[str, set[str]]


class BlockingContext(NamedTuple):
    active_components: dict[str, list[str]]
    substances: dict[str, Substance]
    scheduling_constraint_plans: tuple[SchedulingConstraintExecutionPlan, ...]


class AdvisorySlotEvaluation(NamedTuple):
    """Canonical advisory result for one slot in the winning assignment."""

    penalty: int
    matched_constraint_ids: tuple[str, ...]
