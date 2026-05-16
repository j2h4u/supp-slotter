"""Plan-command feasibility precompute + branch-and-bound search.

Extracted from `planner.engine.plan` to isolate the search loop and its
helpers. This module owns:

- `FeasibilityIndex` NamedTuple + `build_feasibility_index` — derive per-item
  feasible-slot lists, scheduling priority order, slot-score lookup table,
  and the upper-bound remaining-score vector used by B&B pruning.
- `run_plan_search` — greedy seed + first-improvement branch-and-bound
  over the feasibility index, returning the best assignment + metrics.
- `slot_is_blocked` — per-(item, slot) blocking check covering substance-level
  and class-level competes; uses `competes_pairs` for O(1) lookup.

Closures inside `run_plan_search` (`search`, `initialize_best_with_greedy`,
`balance_lower_bound`, `slot_order_key`) intentionally share mutable state
via `nonlocal` — that's the natural form for backtracking, not technical
debt. See decomposition notes in commit history if revisiting.
"""

from __future__ import annotations

import sys
from typing import NamedTuple

from planner.contracts import Relation, Slot, Substance, TraitDef
from planner.engine._plan_inputs import ActiveIndex
from planner.engine._scheduling import compute_slot_score
from planner.io import BALANCE_WEIGHT, PREFER_WITH_BONUS, SECONDARY_TRAIT_WEIGHT


class FeasibilityIndex(NamedTuple):
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]]
    items_by_scheduling_priority: list[str]
    item_id_sequence: list[str]
    slot_score_lookup: dict[str, dict[str, int]]
    remaining_score_upper_bound: list[int]


def build_feasibility_index(
    slots: dict[str, Slot],
    active: ActiveIndex,
    trait_defs: dict[str, TraitDef],
    errors: list[str],
) -> FeasibilityIndex | None:
    """Precompute per-item feasibility + scheduling priority + score bounds.

    Returns a FeasibilityIndex, or None when any item has no feasible slot.
    On failure, the offending item's diagnostic is printed to stderr and
    appended to *errors*.
    """
    feasible_slots_by_item: dict[str, list[tuple[str, int, list[str]]]] = {}
    for sid, traits in active.item_traits.items():
        secondary_traits = active.secondary_traits_by_item[sid]
        # Primary traits drive blocking and base score; secondary-only traits contribute
        # at SECONDARY_TRAIT_WEIGHT and never block.
        # If every component declares primary=False, primary_traits is empty — fall back
        # to scoring with the full effective set so behaviour is unchanged for that
        # pathological product.
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
            # Add secondary-only score contribution at reduced weight (no blocking).
            if secondary_traits:
                sec_score, _sec_blocked, sec_reasons = compute_slot_score(
                    secondary_traits, slot, trait_defs, active.trait_sources_by_item[sid]
                )
                score += int(round(sec_score * SECONDARY_TRAIT_WEIGHT))
                reasons = reasons + sec_reasons
            feasible_slots.append((slot_name, score, reasons))
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
    remaining_score_upper_bound: list[int] = [0] * (len(items_by_scheduling_priority) + 1)
    for index in range(len(items_by_scheduling_priority) - 1, -1, -1):
        item = items_by_scheduling_priority[index]
        remaining_score_upper_bound[index] = remaining_score_upper_bound[index + 1] + max(
            slot_score_lookup[item].values()
        )

    return FeasibilityIndex(
        feasible_slots_by_item=feasible_slots_by_item,
        items_by_scheduling_priority=items_by_scheduling_priority,
        item_id_sequence=item_id_sequence,
        slot_score_lookup=slot_score_lookup,
        remaining_score_upper_bound=remaining_score_upper_bound,
    )


def _compute_assignment_total(
    slot_score_total: int,
    prefer_pairs: set[frozenset[str]],
    assignment: dict[str, str],
    slot_counts: dict[str, int],
) -> tuple[float, int, int, float]:
    """Combine raw slot score with prefer-with bonus and balance penalty.

    Returns (total, slot_score_total, prefer_with_bonus, balance_penalty).
    Pure function — takes everything as parameters, no closure capture.
    """
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
    slot_score_lookup: dict[str, dict[str, int]],
    remaining_score_upper_bound: list[int],
    prefer_pairs: set[frozenset[str]],
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    global_relations: list[Relation],
    competes_pairs: set[frozenset[str]],
) -> tuple[dict[str, str] | None, tuple[float, int, int, float] | None]:
    """Run greedy seed + branch-and-bound search; return (best_assignment, best_metrics).

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
            for slot_name, score, _reasons in sorted(
                feasible_slots_by_item[item],
                key=lambda candidate: (-candidate[1], slot_order[candidate[0]]),
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
        ordered_candidates = sorted(
            feasible_slots_by_item[item],
            key=lambda candidate: (-candidate[1], slot_order[candidate[0]]),
        )
        for slot_name, score, _reasons in ordered_candidates:
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


def slot_is_blocked(
    item: str,
    slot_name: str,
    item_traits: set[str],
    slot_traits: dict[str, list[set[str]]],
    slot_items: dict[str, list[str]],
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    global_relations: list[Relation],
    competes_pairs: set[frozenset[str]],
) -> bool:
    """Return True if item cannot be placed in slot_name due to substance-level competes
    (relations.yaml) or class-level competes (relations.yaml, source_class/target_class).

    `competes_pairs` is the pre-extracted set of unordered substance pairs that
    participate in any `competes` relation; built once per plan via
    `relation_substance_pairs(db, "competes")` and looked up in O(1) here, rather
    than issuing a SurrealQL query per (item, slot, existing) triple.
    """
    # Class-level competes: this is the single documented exception to Planner ↛ knowledge
    # isolation; the scheduler reads substance.is_ ONLY to resolve class membership for
    # class-level competes rules in relations.yaml — see docs/ontology-v2.md §Class-level.
    class_competes = [
        r for r in global_relations
        if r.type == "competes" and r.source_class and r.target_class
    ]
    if class_competes:
        item_classes = {
            cls
            for comp in active_components[item]
            for sub in [substances.get(comp)] if sub
            for cls in sub.is_
        }
        for existing_item in slot_items[slot_name]:
            existing_classes = {
                cls
                for comp in active_components[existing_item]
                for sub in [substances.get(comp)] if sub
                for cls in sub.is_
            }
            for rel in class_competes:
                src, tgt = rel.source_class, rel.target_class
                if (src in item_classes and tgt in existing_classes) or \
                   (tgt in item_classes and src in existing_classes):
                    return True
    # Substance-level competes — O(1) set lookup against pre-extracted pairs.
    item_components = active_components[item]
    for existing_item in slot_items[slot_name]:
        for left in item_components:
            for right in active_components[existing_item]:
                if left != right and frozenset({left, right}) in competes_pairs:
                    return True
    return False
