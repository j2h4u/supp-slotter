"""Branch-and-bound plan search."""

from __future__ import annotations

from typing import NamedTuple

from planner.contracts import SchedulingConstraint, Slot, Substance
from planner.domain_constants import BALANCE_WEIGHT, PREFER_WITH_BONUS
from planner.engine._plan_blocking import slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.scheduling_constraint_matching import advisory_penalty_for_candidate

FLOAT_TIE_EPSILON = 1e-9


class PlanSearchInput(NamedTuple):
    slots: dict[str, Slot]
    items_by_scheduling_priority: list[str]
    item_id_sequence: list[str]
    item_traits: dict[str, set[str]]
    item_stacks: dict[str, str]
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]]
    remaining_score_upper_bound: list[int]
    prefer_pairs: set[frozenset[str]]
    active_components: dict[str, list[str]]
    substances: dict[str, Substance]
    scheduling_constraints: tuple[SchedulingConstraint, ...]


def _compute_assignment_total(
    slot_score_total: int,
    prefer_pairs: set[frozenset[str]],
    assignment: dict[str, str],
    slot_counts: dict[str, int],
) -> tuple[float, int, int, float]:
    prefer_with_bonus = 0
    for pair in prefer_pairs:
        a, b = tuple(pair)
        if assignment.get(a) == assignment.get(b):
            prefer_with_bonus += PREFER_WITH_BONUS
    balance_penalty = BALANCE_WEIGHT * sum(count * count for count in slot_counts.values())
    total = slot_score_total + prefer_with_bonus - balance_penalty
    return total, slot_score_total, prefer_with_bonus, balance_penalty


def run_plan_search(
    search_input: PlanSearchInput,
) -> tuple[dict[str, str] | None, tuple[float, int, int, float] | None]:
    """Run greedy seed + branch-and-bound search.

    Returns (None, None) when no feasible global assignment exists.
    """
    search = _PlanSearch(search_input)
    search.initialize_best_with_greedy()
    search.search(0, 0)
    return search.best_assignment, search.best_metrics


class _PlanSearch:
    input: PlanSearchInput
    slot_order: dict[str, int]
    blocking: BlockingContext
    advisory_constraints: tuple[SchedulingConstraint, ...]

    def __init__(self, search_input: PlanSearchInput) -> None:
        self.input = search_input
        self.slot_order = {slot_name: index for index, slot_name in enumerate(search_input.slots)}
        self.assignment: dict[str, str] = {}
        self.slot_traits: dict[str, list[set[str]]] = {slot_name: [] for slot_name in search_input.slots}
        self.slot_items: dict[str, list[str]] = {slot_name: [] for slot_name in search_input.slots}
        self.slot_counts: dict[str, int] = dict.fromkeys(search_input.slots, 0)
        # Governance is pre-filtered once, outside the hot search loop.  Review
        # and retired records are diagnostics/provenance only and cannot affect
        # slotting even if a caller bypasses the normal loader.
        approved_block = tuple(
            constraint
            for constraint in search_input.scheduling_constraints
            if constraint.status == "approved" and constraint.enforcement == "block" and constraint.evidence
        )
        self.advisory_constraints = tuple(
            constraint
            for constraint in search_input.scheduling_constraints
            if constraint.status == "approved" and constraint.enforcement == "advisory" and constraint.evidence
        )
        self.blocking = BlockingContext(
            active_components=search_input.active_components,
            substances=search_input.substances,
            scheduling_constraints=approved_block,
        )
        self.best_assignment: dict[str, str] | None = None
        self.best_key: tuple[int, ...] | None = None
        self.best_metrics: tuple[float, int, int, float] | None = None

    def slot_order_key(self, candidate_assignment: dict[str, str]) -> tuple[int, ...]:
        return tuple(self.slot_order[candidate_assignment[item]] for item in self.input.item_id_sequence)

    def balance_lower_bound(self, search_index: int) -> float:
        relaxed_counts = dict(self.slot_counts)
        remaining_by_stack: dict[str, int] = {}
        for item in self.input.items_by_scheduling_priority[search_index:]:
            remaining_by_stack[self.input.item_stacks[item]] = (
                remaining_by_stack.get(self.input.item_stacks[item], 0) + 1
            )
        for stack, remaining_count in remaining_by_stack.items():
            stack_slots = [slot_name for slot_name, slot in self.input.slots.items() if slot.stack == stack]
            for _ in range(remaining_count):
                target = min(stack_slots, key=lambda slot_name: relaxed_counts[slot_name])
                relaxed_counts[target] += 1
        return BALANCE_WEIGHT * sum(count * count for count in relaxed_counts.values())

    def initialize_best_with_greedy(self) -> None:
        greedy_assignment: dict[str, str] = {}
        greedy_slot_traits: dict[str, list[set[str]]] = {slot_name: [] for slot_name in self.input.slots}
        greedy_slot_items: dict[str, list[str]] = {slot_name: [] for slot_name in self.input.slots}
        greedy_slot_counts: dict[str, int] = dict.fromkeys(self.input.slots, 0)
        greedy_slot_score = 0
        for item in self.input.items_by_scheduling_priority:
            traits = self.input.item_traits[item]
            chosen: tuple[str, int] | None = None
            for slot_name, score, _reasons, _matched_ids in self.ordered_candidates(item, greedy_slot_items):
                if slot_is_blocked(
                    item,
                    slot_name,
                    greedy_slot_items,
                    self.blocking,
                ):
                    continue
                chosen = slot_name, score
                break
            if chosen is None:
                return
            slot_name, score = chosen
            greedy_assignment[item] = slot_name
            greedy_slot_traits[slot_name].append(traits)
            greedy_slot_items[slot_name].append(item)
            greedy_slot_counts[slot_name] += 1
            greedy_slot_score += score

        self.best_assignment = greedy_assignment
        self.best_metrics = _compute_assignment_total(
            greedy_slot_score, self.input.prefer_pairs, greedy_assignment, greedy_slot_counts
        )
        self.best_key = self.slot_order_key(greedy_assignment)

    def search(self, index: int, slot_score_total: int) -> None:
        if self.best_metrics is not None:
            # Advisory penalties are non-positive, so the existing base-only
            # upper bound remains admissible (if merely looser for pruning).
            optimistic_total = (
                slot_score_total
                + self.input.remaining_score_upper_bound[index]
                + len(self.input.prefer_pairs) * PREFER_WITH_BONUS
                - self.balance_lower_bound(index)
            )
            if optimistic_total < self.best_metrics[0] - FLOAT_TIE_EPSILON:
                return

        if index == len(self.input.items_by_scheduling_priority):
            self._record_candidate(slot_score_total)
            return

        item = self.input.items_by_scheduling_priority[index]
        traits = self.input.item_traits[item]
        for slot_name, score, _reasons, _matched_ids in self.ordered_candidates(item, self.slot_items):
            if slot_is_blocked(
                item,
                slot_name,
                self.slot_items,
                self.blocking,
            ):
                continue
            self._push_assignment(item, slot_name, traits)
            self.search(index + 1, slot_score_total + score)
            self._pop_assignment(item, slot_name)

    def ordered_candidates(
        self,
        item: str,
        slot_items: dict[str, list[str]],
    ) -> list[tuple[str, int, list[str], tuple[str, ...]]]:
        materialized: list[tuple[str, int, list[str], tuple[str, ...]]] = []
        for slot_name, base_score, reasons in self.input.feasible_slots_by_item[item]:
            penalty, matched_ids = advisory_penalty_for_candidate(
                item,
                slot_items.get(slot_name, []),
                self.input.active_components,
                self.input.substances,
                self.advisory_constraints,
            )
            materialized.append((slot_name, base_score + penalty, reasons, matched_ids))
        return sorted(materialized, key=lambda candidate: (-candidate[1], self.slot_order[candidate[0]]))

    def _record_candidate(self, slot_score_total: int) -> None:
        metrics = _compute_assignment_total(
            slot_score_total, self.input.prefer_pairs, self.assignment, self.slot_counts
        )
        candidate_key = self.slot_order_key(self.assignment)
        if not self._is_better_candidate(metrics, candidate_key):
            return
        self.best_metrics = metrics
        self.best_assignment = dict(self.assignment)
        self.best_key = candidate_key

    def _is_better_candidate(self, metrics: tuple[float, int, int, float], candidate_key: tuple[int, ...]) -> bool:
        if self.best_metrics is None:
            return True
        if metrics[0] > self.best_metrics[0] + FLOAT_TIE_EPSILON:
            return True
        return abs(metrics[0] - self.best_metrics[0]) <= FLOAT_TIE_EPSILON and (
            self.best_key is None or candidate_key < self.best_key
        )

    def _push_assignment(self, item: str, slot_name: str, traits: set[str]) -> None:
        self.assignment[item] = slot_name
        self.slot_traits[slot_name].append(traits)
        self.slot_items[slot_name].append(item)
        self.slot_counts[slot_name] += 1

    def _pop_assignment(self, item: str, slot_name: str) -> None:
        self.slot_counts[slot_name] -= 1
        self.slot_items[slot_name].pop()
        self.slot_traits[slot_name].pop()
        del self.assignment[item]
