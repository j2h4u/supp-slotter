from __future__ import annotations

from typing import cast

from planner.contracts import RelationSelector, SchedulingConstraint, Substance
from planner.engine._plan_blocking import blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.schedule_types import ScheduleData, ScheduleSlotEntry
from planner.scheduling_constraint_execution import (
    SchedulingConstraintExecutionPlan,
    compile_scheduling_constraint_execution_plans,
    executable_blocking_plans,
)

from tests.helpers import ontology_bundle
from tests.planner_fixture import flatten_schedule_slots


def _schedule_slots(schedule: ScheduleData) -> dict[str, ScheduleSlotEntry]:
    return cast(dict[str, ScheduleSlotEntry], flatten_schedule_slots(cast(dict[str, object], schedule)))


def test_blocking_entry_points_apply_resolved_constraints() -> None:
    blocking_rule = SchedulingConstraint(
        id="approved",
        source_selector=RelationSelector(entity_id="a"),
        target_selector=RelationSelector(entity_id="b"),
        operation="separate_products_same_slot",
        action="split",
        rationale="r",
    )
    plans = _constraint_plans((blocking_rule,))
    blocking = BlockingContext(
        {"item": ["a"], "existing": ["b"]},
        {"a": Substance("a", "A"), "b": Substance("b", "B")},
        plans,
        ontology_bundle().runtime_program,
    )
    assert tuple(plan.id for plan in executable_blocking_plans(blocking.scheduling_constraint_plans)) == ("approved",)
    assert slot_is_blocked("item", "slot", {"slot": ["existing"]}, blocking)
    diagnostics = blocking_constraint_diagnostics("item", "slot", {"slot": ["existing"]}, blocking)
    assert diagnostics[0].id == "approved"
    assert diagnostics[0].metadata["rationale"] == "r"


def _constraint_plans(
    constraints: tuple[SchedulingConstraint, ...],
) -> tuple[SchedulingConstraintExecutionPlan, ...]:
    return compile_scheduling_constraint_execution_plans(
        constraints,
        {"a": Substance("a", "A"), "b": Substance("b", "B")},
        ontology_bundle().runtime_program,
        ontology_bundle=ontology_bundle(),
    )
