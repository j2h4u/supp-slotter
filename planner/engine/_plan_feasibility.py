"""Feasibility precompute for the plan command."""

from __future__ import annotations

import sys
from typing import NamedTuple

from planner.contracts import Slot, TraitDef
from planner.domain_constants import SECONDARY_TRAIT_WEIGHT
from planner.engine._plan_types import ActiveIndex
from planner.engine._scheduling import compute_slot_score


class FeasibilityIndex(NamedTuple):
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]]
    items_by_scheduling_priority: list[str]
    item_id_sequence: list[str]
    remaining_score_upper_bound: list[int]


def build_feasibility_index(
    slots: dict[str, Slot],
    active: ActiveIndex,
    trait_defs: dict[str, TraitDef],
    errors: list[str],
) -> FeasibilityIndex | None:
    """Precompute per-item feasible slots, priority order, and score bounds."""
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]] = {}
    for sid, traits in active.item_traits.items():
        feasible_slots = _feasible_slots_for_item(sid, traits, slots, active, trait_defs)
        if not feasible_slots:
            msg = f"plan: stack item '{sid}' is blocked from every slot."
            print(msg, file=sys.stderr)
            errors.append(msg)
            return None
        feasible_slots.sort(key=lambda c: -c[1])
        feasible_slots_by_item[sid] = feasible_slots

    item_id_sequence = list(active.item_traits)
    items_by_scheduling_priority = sorted(
        active.item_traits,
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
        feasible_slots_by_item=feasible_slots_by_item,
        items_by_scheduling_priority=items_by_scheduling_priority,
        item_id_sequence=item_id_sequence,
        remaining_score_upper_bound=remaining_score_upper_bound,
    )


def _feasible_slots_for_item(
    sid: str,
    traits: set[str],
    slots: dict[str, Slot],
    active: ActiveIndex,
    trait_defs: dict[str, TraitDef],
) -> list[tuple[str, int, list[str]]]:
    secondary_traits = active.secondary_traits_by_item[sid]
    primary_traits = traits - secondary_traits
    score_traits = primary_traits if primary_traits else traits

    feasible_slots: list[tuple[str, int, list[str]]] = []
    for slot_name, slot in slots.items():
        if slot.stack != active.item_stacks[sid]:
            continue
        score, blocked, reasons = compute_slot_score(
            score_traits, slot, trait_defs, active.trait_sources_by_item[sid]
        )
        if blocked:
            continue
        if secondary_traits:
            sec_score, _sec_blocked, sec_reasons = compute_slot_score(
                secondary_traits, slot, trait_defs, active.trait_sources_by_item[sid]
            )
            score += int(round(sec_score * SECONDARY_TRAIT_WEIGHT))
            reasons = reasons + sec_reasons
        feasible_slots.append((slot_name, score, reasons))
    return feasible_slots


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
