"""Slot blocking checks for plan search."""

from __future__ import annotations

from typing import NamedTuple

from planner.engine._plan_types import BlockingContext
from planner.scheduling_constraint_execution import (
    SchedulingConstraintExecutionPlan,
    interpret_constraint_component_pair,
)


class _SchedulingConstraintContext(NamedTuple):
    slot_items: dict[str, list[str]]
    active_components: dict[str, list[str]]
    constraints: tuple[SchedulingConstraintExecutionPlan, ...]


class SchedulingConstraintDiagnostic(NamedTuple):
    """Stable explanation of a hard constraint that blocked a candidate slot."""

    id: str
    action: str | None
    metadata: dict[str, object]


def slot_is_blocked(
    item: str,
    slot_name: str,
    slot_items: dict[str, list[str]],
    blocking: BlockingContext,
) -> bool:
    """Return True if placing an item violates a first-class block constraint."""
    constraints_context = _SchedulingConstraintContext(
        slot_items=slot_items,
        active_components=blocking.active_components,
        constraints=_approved_block_constraints(blocking),
    )
    return _scheduling_constraint_blocks_item(
        item,
        slot_name,
        constraints_context,
    )


def blocking_constraint_diagnostics(
    item: str,
    slot_name: str,
    slot_items: dict[str, list[str]],
    blocking: BlockingContext,
) -> tuple[SchedulingConstraintDiagnostic, ...]:
    """Return matching hard constraints, preserving boolean blocking parity.

    This is intentionally separate from :func:`slot_is_blocked` so the planner's
    hot search loop keeps its allocation-free boolean path.
    """
    context = _SchedulingConstraintContext(
        slot_items=slot_items,
        active_components=blocking.active_components,
        constraints=_approved_block_constraints(blocking),
    )
    matches = _matching_constraints(item, slot_name, context)
    return tuple(
        SchedulingConstraintDiagnostic(
            id=constraint.id,
            action=constraint.action,
            metadata={
                "rationale": constraint.rationale,
            },
        )
        for constraint in matches
    )


def _scheduling_constraint_blocks_item(
    item: str,
    slot_name: str,
    context: _SchedulingConstraintContext,
) -> bool:
    if not context.constraints:
        return False

    item_components = context.active_components.get(item, ())
    for existing_item in context.slot_items.get(slot_name, []):
        existing_components = context.active_components.get(existing_item, ())
        for constraint in context.constraints:
            if interpret_constraint_component_pair(
                constraint,
                item_components,
                existing_components,
                context.runtime_program,
            ):
                return True
    return False


def _matching_constraints(
    item: str,
    slot_name: str,
    context: _SchedulingConstraintContext,
) -> tuple[SchedulingConstraintExecutionPlan, ...]:
    if not context.constraints:
        return ()

    item_components = context.active_components.get(item, ())
    matched: list[SchedulingConstraintExecutionPlan] = []
    for existing_item in context.slot_items.get(slot_name, []):
        existing_components = context.active_components.get(existing_item, ())
        for constraint in context.constraints:
            if (
                interpret_constraint_component_pair(
                    constraint,
                    item_components,
                    existing_components,
                    context.runtime_program,
                )
                and constraint not in matched
            ):
                matched.append(constraint)
    return tuple(matched)


def _approved_block_constraints(
    blocking: BlockingContext,
) -> tuple[SchedulingConstraintExecutionPlan, ...]:
    """Select executable hard-block plans from the compiled runtime contract."""
    return tuple(plan for plan in blocking.scheduling_constraint_plans if plan.executable and plan.blocks_slots)
