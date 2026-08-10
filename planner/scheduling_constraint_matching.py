"""Shared deterministic selector matching for scheduling diagnostics and coverage."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

from planner.scheduling_constraint_execution import (
    SchedulingConstraintExecutionPlan,
    interpret_constraint_component_pair,
)


def advisory_penalty_for_candidate(
    item_id: str,
    existing_slot_item_ids: list[str] | tuple[str, ...],
    active_components: dict[str, list[str]],
    advisory_constraints: tuple[SchedulingConstraintExecutionPlan, ...],
) -> tuple[int, tuple[str, ...]]:
    """Return deterministic advisory penalties for a candidate and slot state.

    Matching and per-rule score contribution come from the verified runtime
    scoring contract; callers may use the returned IDs for diagnostics only.
    """
    before_penalty, before_ids = advisory_penalty_for_slot(
        existing_slot_item_ids,
        active_components,
        advisory_constraints,
    )
    after_penalty, after_ids = advisory_penalty_for_slot(
        (*existing_slot_item_ids, item_id),
        active_components,
        advisory_constraints,
    )
    introduced_ids = tuple(sorted(set(after_ids) - set(before_ids)))
    return after_penalty - before_penalty, introduced_ids


def advisory_penalty_for_slot(
    slot_item_ids: Sequence[str],
    active_components: dict[str, list[str]],
    advisory_constraints: tuple[SchedulingConstraintExecutionPlan, ...],
) -> tuple[int, tuple[str, ...]]:
    """Evaluate advisory rules once per slot, independently of item order."""
    canonical_item_ids = tuple(sorted(set(slot_item_ids)))
    matched: set[str] = set()
    penalty = 0
    for left_id, right_id in combinations(canonical_item_ids, 2):
        for constraint in sorted(advisory_constraints, key=lambda item: item.id):
            if not (constraint.executable and constraint.scores_advisory):
                continue
            if (
                interpret_constraint_component_pair(
                    constraint,
                    active_components.get(left_id, []),
                    active_components.get(right_id, []),
                )
                and constraint.id not in matched
            ):
                matched.add(constraint.id)
                penalty += _score_delta(constraint)
    return penalty, tuple(sorted(matched))


def _score_delta(constraint: SchedulingConstraintExecutionPlan) -> int:
    return constraint.score_delta
