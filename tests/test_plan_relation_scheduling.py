from __future__ import annotations

from typing import cast

from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.engine._plan_blocking import _approved_block_constraints, blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.schedule_types import ScheduleData, ScheduleSlotEntry
from planner.scheduling_constraint_execution import (
    SchedulingConstraintExecutionPlan,
    compile_scheduling_constraint_execution_plans,
)

from tests.helpers import ontology_bundle
from tests.planner_fixture import flatten_schedule_slots


def _schedule_slots(schedule: ScheduleData) -> dict[str, ScheduleSlotEntry]:
    return cast(dict[str, ScheduleSlotEntry], flatten_schedule_slots(cast(dict[str, object], schedule)))


def test_blocking_entry_points_filter_unapproved_and_non_block_constraints() -> None:
    approved = SchedulingConstraint(
        id="approved",
        source_selector=RelationSelector(entity_id="a"),
        target_selector=RelationSelector(entity_id="b"),
        operation="separate_products_same_slot",
        enforcement="block",
        status="approved",
        evidence=("e",),
        action="split",
        rationale="r",
        semantic_note="n",
        owner="o",
        review_by="d",
        assertion_type="direct",
    )
    rejected = approved.__class__(
        id="rejected",
        source_selector=approved.source_selector,
        target_selector=approved.target_selector,
        operation="separate_products_same_slot",
        enforcement="block",
        status="review_pending",
        evidence=("e",),
    )
    advisory = approved.__class__(
        id="advisory",
        source_selector=approved.source_selector,
        target_selector=approved.target_selector,
        operation="separate_products_same_slot",
        enforcement="advisory",
        status="approved",
        evidence=("e",),
    )
    plans = _constraint_plans((approved, rejected, advisory))
    blocking = BlockingContext(
        {"item": ["a"], "existing": ["b"]},
        {"a": Substance("a", "A"), "b": Substance("b", "B")},
        plans,
    )
    assert tuple(plan.id for plan in _approved_block_constraints(blocking)) == ("approved",)
    assert slot_is_blocked("item", "slot", {"slot": ["existing"]}, blocking)
    diagnostics = blocking_constraint_diagnostics("item", "slot", {"slot": ["existing"]}, blocking)
    assert diagnostics[0].id == "approved"
    assert diagnostics[0].metadata["semantic_note"] == "n"


def _constraint_plans(
    constraints: tuple[SchedulingConstraint, ...],
) -> tuple[SchedulingConstraintExecutionPlan, ...]:
    return compile_scheduling_constraint_execution_plans(
        constraints,
        {"a": Substance("a", "A"), "b": Substance("b", "B")},
        ontology_bundle().runtime_program,
    )
