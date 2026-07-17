"""Feasibility precompute for the plan command."""

from __future__ import annotations

import sys
from typing import NamedTuple

from planner.contracts import SchedulingPolicy, Slot, SlotCandidateTrace
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import compute_slot_score
from planner.ontology.runtime_program import RuntimeProgram


class FeasibilityIndex(NamedTuple):
    candidate_traces_by_item: dict[str, tuple[SlotCandidateTrace, ...]]
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]]
    items_by_scheduling_priority: list[str]
    item_id_sequence: list[str]
    remaining_score_upper_bound: list[int]


def build_feasibility_index(
    runtime_program: RuntimeProgram,
    slots: dict[str, Slot],
    active: ActiveIndex,
    policies: dict[str, SchedulingPolicy],
    errors: list[str],
) -> FeasibilityIndex | None:
    """Precompute per-item feasible slots, priority order, and score bounds."""
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]] = {}
    candidate_traces_by_item: dict[str, tuple[SlotCandidateTrace, ...]] = {}
    for sid in active.item_products:
        candidate_traces = _candidate_traces_for_item(runtime_program, sid, slots, active, policies)
        candidate_traces_by_item[sid] = candidate_traces
        feasible_slots = [
            (trace.slot_id, trace.score, [diagnostic.code for diagnostic in trace.diagnostics])
            for trace in candidate_traces
            if not trace.blocked
        ]
        if not feasible_slots:
            contributors = sorted({triple for trace in candidate_traces for triple in trace.block_contributors})
            assert contributors, "blocked candidates must retain controlling assignment contributors"
            encoded = ";".join("|".join(triple) for triple in contributors)
            msg = f"plan: stack item '{sid}' is blocked from every slot. [BLOCKED_ALL_SLOTS: {encoded}]"
            print(msg, file=sys.stderr)
            errors.append(msg)
            return None
        feasible_slots.sort(key=lambda c: -c[1])
        feasible_slots_by_item[sid] = feasible_slots

    item_id_sequence = list(active.item_products)
    items_by_scheduling_priority = sorted(
        active.item_products,
        key=lambda item: (
            len(feasible_slots_by_item[item]),
            -max(score for _slot_name, score, _reasons in feasible_slots_by_item[item]),
            item_id_sequence.index(item),
        ),
    )
    slot_score_lookup = {
        item: {slot_name: score for slot_name, score, _reasons in item_candidates}
        for item, item_candidates in feasible_slots_by_item.items()
    }
    remaining_score_upper_bound = _remaining_score_upper_bound(
        items_by_scheduling_priority,
        slot_score_lookup,
    )

    return FeasibilityIndex(
        candidate_traces_by_item=candidate_traces_by_item,
        feasible_slots_by_item=feasible_slots_by_item,
        items_by_scheduling_priority=items_by_scheduling_priority,
        item_id_sequence=item_id_sequence,
        remaining_score_upper_bound=remaining_score_upper_bound,
    )


def _candidate_traces_for_item(
    runtime_program: RuntimeProgram,
    sid: str,
    slots: dict[str, Slot],
    active: ActiveIndex,
    policies: dict[str, SchedulingPolicy],
) -> tuple[SlotCandidateTrace, ...]:
    candidates: list[SlotCandidateTrace] = []
    projection = active.governed_projection_by_item[sid]
    row_by_id = {row.assignment_id: row for row in projection.assignments}
    for slot_name, slot in slots.items():
        if slot.stack != active.item_stacks[sid]:
            continue
        trace = compute_slot_score(runtime_program, projection, slot, policies)
        contributors = {
            (effect.policy_id, assignment_id, row_by_id[assignment_id].source_card_id)
            for effect in trace.effects
            if effect.projected_block
            for assignment_id in effect.assignment_ids
        }
        candidates.append(
            SlotCandidateTrace(
                slot_id=slot_name,
                score=trace.score,
                blocked=trace.blocked,
                effects=trace.effects,
                diagnostics=trace.diagnostics,
                block_contributors=tuple(sorted(contributors)),
            )
        )
    return tuple(candidates)


def _remaining_score_upper_bound(
    items_by_scheduling_priority: list[str],
    slot_score_lookup: dict[str, dict[str, int]],
) -> list[int]:
    remaining_score_upper_bound: list[int] = [0] * (len(items_by_scheduling_priority) + 1)
    for index in range(len(items_by_scheduling_priority) - 1, -1, -1):
        item = items_by_scheduling_priority[index]
        remaining_score_upper_bound[index] = remaining_score_upper_bound[index + 1] + max(
            slot_score_lookup[item].values()
        )
    return remaining_score_upper_bound
