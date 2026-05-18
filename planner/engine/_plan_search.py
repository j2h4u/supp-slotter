"""Branch-and-bound plan search."""

from __future__ import annotations

from planner.contracts import Relation, Slot, Substance, TraitDef
from planner.domain_constants import BALANCE_WEIGHT, PREFER_WITH_BONUS
from planner.engine._plan_blocking import slot_is_blocked


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
    balance_penalty = BALANCE_WEIGHT * sum(
        count * count for count in slot_counts.values()
    )
    total = slot_score_total + prefer_with_bonus - balance_penalty
    return total, slot_score_total, prefer_with_bonus, balance_penalty


def run_plan_search(
    *,
    slots: dict[str, Slot],
    items_by_scheduling_priority: list[str],
    item_id_sequence: list[str],
    item_traits: dict[str, set[str]],
    item_stacks: dict[str, str],
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]],
    remaining_score_upper_bound: list[int],
    prefer_pairs: set[frozenset[str]],
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    global_relations: list[Relation],
    competes_pairs: set[frozenset[str]],
) -> tuple[dict[str, str] | None, tuple[float, int, int, float] | None]:
    """Run greedy seed + branch-and-bound search.

    Returns (None, None) when no feasible global assignment exists.
    """
    slot_names = list(slots)
    slot_order = {slot_name: index for index, slot_name in enumerate(slot_names)}

    assignment: dict[str, str] = {}
    slot_traits: dict[str, list[set[str]]] = {slot_name: [] for slot_name in slots}
    slot_items: dict[str, list[str]] = {slot_name: [] for slot_name in slots}
    slot_counts: dict[str, int] = {slot_name: 0 for slot_name in slots}
    best_assignment: dict[str, str] | None = None
    best_key: tuple[int, ...] | None = None
    best_metrics: tuple[float, int, int, float] | None = None

    def slot_order_key(candidate_assignment: dict[str, str]) -> tuple[int, ...]:
        return tuple(slot_order[candidate_assignment[item]] for item in item_id_sequence)

    def balance_lower_bound(search_index: int) -> float:
        relaxed_counts = dict(slot_counts)
        remaining_by_stack: dict[str, int] = {}
        for item in items_by_scheduling_priority[search_index:]:
            remaining_by_stack[item_stacks[item]] = remaining_by_stack.get(
                item_stacks[item], 0
            ) + 1
        for stack, remaining_count in remaining_by_stack.items():
            stack_slots = [
                slot_name
                for slot_name, slot in slots.items()
                if slot.stack == stack
            ]
            for _ in range(remaining_count):
                target = min(stack_slots, key=lambda slot_name: relaxed_counts[slot_name])
                relaxed_counts[target] += 1
        return BALANCE_WEIGHT * sum(count * count for count in relaxed_counts.values())

    def initialize_best_with_greedy() -> None:
        nonlocal best_assignment, best_key, best_metrics

        greedy_assignment: dict[str, str] = {}
        greedy_slot_traits: dict[str, list[set[str]]] = {
            slot_name: [] for slot_name in slots
        }
        greedy_slot_items: dict[str, list[str]] = {slot_name: [] for slot_name in slots}
        greedy_slot_counts: dict[str, int] = {slot_name: 0 for slot_name in slots}
        greedy_slot_score = 0
        for item in items_by_scheduling_priority:
            traits = item_traits[item]
            chosen: tuple[str, int] | None = None
            for slot_name, score, _reasons in _ordered_candidates(
                item, feasible_slots_by_item, slot_order
            ):
                if slot_is_blocked(
                    item, slot_name, traits,
                    greedy_slot_traits, greedy_slot_items,
                    active_components, substances, trait_defs, global_relations,
                    competes_pairs,
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

        best_assignment = greedy_assignment
        best_metrics = _compute_assignment_total(
            greedy_slot_score, prefer_pairs, greedy_assignment, greedy_slot_counts
        )
        best_key = slot_order_key(greedy_assignment)

    def search(index: int, slot_score_total: int) -> None:
        nonlocal best_assignment, best_key, best_metrics

        if best_metrics is not None:
            optimistic_total = (
                slot_score_total
                + remaining_score_upper_bound[index]
                + len(prefer_pairs) * PREFER_WITH_BONUS
                - balance_lower_bound(index)
            )
            if optimistic_total < best_metrics[0] - 1e-9:
                return

        if index == len(items_by_scheduling_priority):
            metrics = _compute_assignment_total(
                slot_score_total, prefer_pairs, assignment, slot_counts
            )
            candidate_key = slot_order_key(assignment)
            if (
                best_metrics is None
                or metrics[0] > best_metrics[0] + 1e-9
                or (
                    abs(metrics[0] - best_metrics[0]) <= 1e-9
                    and (best_key is None or candidate_key < best_key)
                )
            ):
                best_metrics = metrics
                best_assignment = dict(assignment)
                best_key = candidate_key
            return

        item = items_by_scheduling_priority[index]
        traits = item_traits[item]
        for slot_name, score, _reasons in _ordered_candidates(
            item, feasible_slots_by_item, slot_order
        ):
            if slot_is_blocked(
                item, slot_name, traits,
                slot_traits, slot_items,
                active_components, substances, trait_defs, global_relations,
                competes_pairs,
            ):
                continue
            assignment[item] = slot_name
            slot_traits[slot_name].append(traits)
            slot_items[slot_name].append(item)
            slot_counts[slot_name] += 1
            search(index + 1, slot_score_total + score)
            slot_counts[slot_name] -= 1
            slot_items[slot_name].pop()
            slot_traits[slot_name].pop()
            del assignment[item]

    initialize_best_with_greedy()
    search(0, 0)

    return best_assignment, best_metrics


def _ordered_candidates(
    item: str,
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]],
    slot_order: dict[str, int],
) -> list[tuple[str, int, list[str]]]:
    return sorted(
        feasible_slots_by_item[item],
        key=lambda candidate: (-candidate[1], slot_order[candidate[0]]),
    )
