"""`plan` command: build schedule.yaml via slot-assignment search."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from planner.cards.dashboards import build_dashboard_review
from planner.cards.pillboxes import (
    build_empty_schedule_pillboxes,
    flatten_pillbox_slots,
    load_pillboxes,
)
from planner.cards.product import (
    collect_product_substance_refs,
    format_item_product_name,
    load_product_registry,
    product_component_substances,
)
from planner.cards.relations import (
    collect_intra_product_relation_conflicts,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    component_sets_have_relation,
    load_global_relations,
)
from planner.cards.schedule import (
    build_action_points,
    build_placement_notes,
    build_schedule_summary,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.cards.traits import load_traits, readable_traits
from planner.cards.warnings import (
    build_review_contexts,
    collect_active_unmatched_concerns,
    humanize_warning,
    is_generic_manual_review_warning,
)
from planner.contracts import Relation, Slot, Substance, TraitDef
from planner.engine._scheduling import (
    build_substance_slot_names,
    compute_slot_score,
    effective_stack_item_traits,
    explain_slot_choice,
    must_separate,
)
from planner.engine.check import cmd_check
from planner.io import (
    BALANCE_WEIGHT,
    DASHBOARDS_DIR,
    DATA_DIR,
    PREFER_WITH_BONUS,
    SCHEDULE_PATH,
    STACKS_PATH,
    dump_schedule_yaml,
    load_yaml,
)


def _load_plan_inputs(
    data_dir: Path,
) -> (
    tuple[
        dict[str, Slot],
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        list[Relation],
        list[Any],
        dict[str, Any],
        Any,
    ]
    | None
):
    """Load all static inputs needed before the active-index build.

    Returns (slots, trait_defs, substances, products, global_relations,
    dashboard_files, stack_entries, pillboxes) or None on failure.
    """
    pillboxes = load_pillboxes(data_dir / "pillboxes.yaml")
    trait_defs = load_traits(data_dir / "traits.yaml")
    stacks_data = load_yaml(STACKS_PATH)

    if not isinstance(stacks_data, dict):
        print("plan: stacks.yaml: top-level must be a mapping", file=sys.stderr)
        return None

    stacks_dict = cast(dict[str, Any], stacks_data)
    slots: dict[str, Slot] = dict(
        sorted(
            flatten_pillbox_slots(pillboxes).items(),
            key=lambda kv: (kv[1].pillbox, kv[1].order),
        )
    )

    substances = load_substance_registry()
    products = load_product_registry()
    global_relations = load_global_relations()
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []
    stack_entries = normalize_stack_entries(stacks_dict)

    return slots, trait_defs, substances, products, global_relations, dashboard_files, stack_entries, pillboxes


def _build_active_index(
    stack_entries: dict[str, Any],
    products: dict[str, Any],
    substances: dict[str, Any],
    trait_defs: dict[str, Any],
    global_relations: list[Relation],
    slots: dict[str, Slot],
) -> (
    tuple[
        dict[str, set[str]],
        dict[str, str],
        dict[str, list[str]],
        dict[str, dict[str, list[str]]],
        dict[str, list[dict[str, Any]]],
        dict[str, list[dict[str, Any]]],
        dict[str, str],
    ]
    | None
):
    """Build per-item trait/conflict/stack indexes from the active stack entries.

    Returns (active, item_products, active_components, trait_sources_by_item,
    intra_product_conflicts_by_item, intra_product_relation_conflicts_by_item,
    item_stacks) or None if any early-exit condition is hit.
    """
    active: dict[str, set[str]] = {}
    item_products: dict[str, str] = {}
    active_components: dict[str, list[str]] = {}
    trait_sources_by_item: dict[str, dict[str, list[str]]] = {}
    intra_product_conflicts_by_item: dict[str, list[dict[str, Any]]] = {}
    intra_product_relation_conflicts_by_item: dict[str, list[dict[str, Any]]] = {}
    item_stacks: dict[str, str] = {}

    for item_id, entry in stack_entries.items():
        stack = entry.get("stack")
        if stack == "inactive":
            continue
        product_id = entry.get("product")
        product = products.get(product_id) if isinstance(product_id, str) else None
        if product is None or not isinstance(product_id, str):
            print(
                f"plan: skipping '{item_id}' — product '{product_id}' missing or invalid",
                file=sys.stderr,
            )
            continue
        effective, trait_sources, internal_conflicts = effective_stack_item_traits(
            product, substances, trait_defs
        )
        active[item_id] = effective
        item_products[item_id] = product_id
        active_components[item_id] = product_component_substances(product)
        trait_sources_by_item[item_id] = trait_sources
        intra_product_conflicts_by_item[item_id] = internal_conflicts
        intra_product_relation_conflicts_by_item[item_id] = (
            collect_intra_product_relation_conflicts(
                item_id=item_id,
                product_id=product_id,
                component_ids=active_components[item_id],
                substances=substances,
                relation_type="competes",
                global_relations=global_relations,
            )
        )
        item_stacks[item_id] = stack if isinstance(stack, str) else ""

    if not active:
        print("plan: no non-inactive stack items.", file=sys.stderr)
        return None

    workout_stacks = {
        slot.stack
        for slot in slots.values()
        if slot.near.startswith("workout_")
    }
    for item_id, traits in active.items():
        activity_traits = sorted(trait for trait in traits if trait.startswith("activity:"))
        if activity_traits and item_stacks[item_id] not in workout_stacks:
            print(
                f"plan: stack item '{item_id}' has {', '.join(activity_traits)} "
                f"but stack '{item_stacks[item_id]}' has no workout pillbox slots.",
                file=sys.stderr,
            )
            return None

    return (
        active,
        item_products,
        active_components,
        trait_sources_by_item,
        intra_product_conflicts_by_item,
        intra_product_relation_conflicts_by_item,
        item_stacks,
    )


def _resolve_prefer_pairs(
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    substances: dict[str, Any],
) -> tuple[set[frozenset[str]], list[dict[str, Any]], dict[str, list[str]]]:
    """Build prefer_pairs, ambiguous warnings, and substance-to-active-items index.

    Returns (prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items).
    """
    prefer_pairs: set[frozenset[str]] = set()
    ambiguous_prefer_with_warnings: list[dict[str, Any]] = []
    substance_to_active_items: dict[str, list[str]] = {}

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance_to_active_items.setdefault(component_id, []).append(item_id)
    for component_id in substance_to_active_items:
        substance_to_active_items[component_id].sort()

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance = substances.get(component_id)
            if substance is None:
                continue
            for target_substance in substance.prefer_with:
                target_items = substance_to_active_items.get(target_substance, [])
                if len(target_items) == 1:
                    other_item = target_items[0]
                    if other_item != item_id:
                        prefer_pairs.add(frozenset([item_id, other_item]))
                elif len(target_items) > 1:
                    ambiguous_prefer_with_warnings.append(
                        {
                            "type": "ambiguous_prefer_with",
                            "item": item_id,
                            "product": item_products[item_id],
                            "source_substance": component_id,
                            "target_substance": target_substance,
                            "candidate_items": target_items,
                            "message": (
                                "prefer_with target maps to multiple active "
                                "stack items; no bonus awarded"
                            ),
                        }
                    )

    return prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items


def _build_schedule_output(
    assignment: dict[str, str],
    best_metrics: tuple[float, int, int, float],
    slots: dict[str, Slot],
    active_order: list[str],
    active_components: dict[str, list[str]],
    item_products: dict[str, str],
    products: dict[str, Any],
    substances: dict[str, Any],
    relations: list[Relation],
    trait_defs: dict[str, Any],
    prefer_pairs: set[frozenset[str]],
    substance_to_active_items: dict[str, list[str]],
    stack_entries: dict[str, Any],
    dashboard_files: list[Any],
    intra_product_conflicts_by_item: dict[str, list[dict[str, Any]]],
    intra_product_relation_conflicts_by_item: dict[str, list[dict[str, Any]]],
    trait_sources_by_item: dict[str, dict[str, list[str]]],
    active: dict[str, set[str]],
    pillboxes: Any,
    warnings_prefix: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the complete schedule dict from a solved assignment.

    Returns the schedule dict ready to be serialised (excluding the write step).
    """
    schedule: dict[str, Any] = {
        "summary": {},
        "action_points": [],
        "review_contexts": [],
        "placement_notes": [],
        "pillboxes": build_empty_schedule_pillboxes(pillboxes),
        "benefits": [],
        "risks": [],
        "warnings": [],
        "kept_together": [
            {
                "pair": sorted(
                    [
                        format_item_product_name(item_id, item_products, products)
                        for item_id in sorted(p)
                    ],
                    key=str.casefold,
                ),
                "together": (
                    assignment[sorted(p)[0]] == assignment[sorted(p)[1]]
                ),
                "slot": assignment[sorted(p)[0]]
                if assignment[sorted(p)[0]] == assignment[sorted(p)[1]]
                else None,
            }
            for p in (sorted(prefer_pairs, key=lambda x: sorted(x)))
        ],
        "explanations": {},
    }

    for sid in active_order:
        slot_name = assignment[sid]
        pillbox_name = slots[slot_name].pillbox
        schedule["pillboxes"][pillbox_name]["slots"][slot_name]["products"].append(
            format_item_product_name(sid, item_products, products)
        )
    for pillbox in schedule["pillboxes"].values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"] = sorted(slot_entry["products"], key=str.casefold)

    for slot_name, slot in slots.items():
        pillbox_name = slot.pillbox
        slot_entry = schedule["pillboxes"][pillbox_name]["slots"][slot_name]
        slot_item_ids = [
            item_id for item_id in active_order if assignment[item_id] == slot_name
        ]
        slot_entry["substances"] = build_substance_slot_names(
            slot_items=slot_item_ids,
            item_products=item_products,
            products=products,
            substances=substances,
        )

    active_substance_ids = set(substance_to_active_items)
    inactive_product_ids = {
        entry["product"]
        for entry in stack_entries.values()
        if entry.get("stack") == "inactive" and isinstance(entry.get("product"), str)
    }
    inactive_substance_ids = collect_product_substance_refs(products, inactive_product_ids)
    cluster_review = build_dashboard_review(
        dashboard_files=dashboard_files,
        active_substances=active_substance_ids,
        inactive_substances=inactive_substance_ids,
        substances=substances,
    )
    schedule["benefits"] = cluster_review["benefits"]
    schedule["risks"] = cluster_review["risks"]
    schedule["warnings"].extend(cluster_review["warnings"])

    for sid in active_order:
        slot_name = assignment[sid]
        slot = slots[slot_name]
        product_name = format_item_product_name(sid, item_products, products)
        components_list: list[str] = []
        for substance_id in active_components[sid]:
            substance_dc = substances.get(substance_id)
            if substance_dc is not None:
                components_list.append(format_substance_name(substance_dc))
            else:
                components_list.append(substance_id)
        schedule["explanations"][product_name] = {
            "components": components_list,
            "pillbox": slot.pillbox,
            "slot": slot_name,
            "why_here": explain_slot_choice(active[sid], slot, trait_defs),
            "review_tags": readable_traits(active[sid], trait_defs),
        }

    for sid, internal_conflicts in intra_product_conflicts_by_item.items():
        for conflict in internal_conflicts:
            schedule["warnings"].append(
                {
                    "type": "intra_product_trait_conflict",
                    "item": sid,
                    "product": item_products[sid],
                    "trait": conflict["trait"],
                    "conflicts_with": conflict["conflicts_with"],
                    "substances": conflict["substances"],
                    "conflicting_substances": conflict["conflicting_substances"],
                    "message": (
                        "Component traits conflict inside one physical product; "
                        "scheduling keeps the product together and emits this warning"
                    ),
                }
            )
    for _sid, internal_conflicts in intra_product_relation_conflicts_by_item.items():
        for conflict in internal_conflicts:
            schedule["warnings"].append(conflict)

    schedule["warnings"].extend(
        collect_active_unmatched_concerns(
            active_order=active_order,
            active_components=active_components,
            item_products=item_products,
            products=products,
            substances=substances,
        )
    )
    schedule["warnings"].extend(warnings_prefix)

    for sid, traits in active.items():
        for trait_id in sorted(traits):
            trait_def = trait_defs.get(trait_id)
            if trait_def is not None and trait_def.warning:
                for source in trait_sources_by_item[sid].get(trait_id) or ["unknown"]:
                    schedule["warnings"].append(
                        {
                            "item": sid,
                            "product": item_products[sid],
                            "substance": source,
                            "trait": trait_id,
                            "message": trait_def.description or "Manual review required.",
                            "action": trait_def.action or "",
                        }
                    )

    for warning in collect_missing_balance_relations(
        substances, active_substance_ids, relations
    ):
        schedule["warnings"].append(warning)
    for warning in collect_missing_support_relations(
        substances, active_substance_ids, relations
    ):
        schedule["warnings"].append(warning)

    schedule["warnings"] = [
        humanize_warning(warning, products=products, substances=substances)
        for warning in schedule["warnings"]
        if not is_generic_manual_review_warning(warning)
    ]
    schedule["action_points"] = build_action_points(schedule["warnings"])
    schedule["review_contexts"] = build_review_contexts(schedule["warnings"])
    schedule["placement_notes"] = build_placement_notes(schedule)
    schedule["summary"] = build_schedule_summary(schedule)

    return schedule


def _slot_is_blocked(
    item: str,
    slot_name: str,
    item_traits: set[str],
    slot_traits: dict[str, list[set[str]]],
    slot_items: dict[str, list[str]],
    active_components: dict[str, list[str]],
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
    global_relations: list[Relation],
) -> bool:
    """Return True if item cannot be placed in slot_name due to trait or competes conflict."""
    if any(
        must_separate(item_traits, existing_traits, trait_defs)
        for existing_traits in slot_traits[slot_name]
    ):
        return True
    if any(
        component_sets_have_relation(
            active_components[item],
            active_components[existing_item],
            substances,
            "competes",
            global_relations,
        )
        for existing_item in slot_items[slot_name]
    ):
        return True
    return False


def cmd_plan() -> int:
    print("=== running check ===", file=sys.stderr)
    check_result = cmd_check()
    if check_result != 0:
        print("plan aborted: check failed; fix errors above and retry.", file=sys.stderr)
        return check_result
    print("=== check passed; building schedule ===", file=sys.stderr)

    result = _load_plan_inputs(DATA_DIR)
    if result is None:
        return 1
    slots, trait_defs, substances, products, global_relations, dashboard_files, stack_entries, pillboxes = result

    index_result = _build_active_index(
        stack_entries, products, substances, trait_defs, global_relations, slots
    )
    if index_result is None:
        return 1
    (
        active,
        item_products,
        active_components,
        trait_sources_by_item,
        intra_product_conflicts_by_item,
        intra_product_relation_conflicts_by_item,
        item_stacks,
    ) = index_result

    prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items = (
        _resolve_prefer_pairs(active_components, item_products, substances)
    )

    candidates: dict[str, list[tuple[str, int, list[str]]]] = {}
    for sid, traits in active.items():
        valid: list[tuple[str, int, list[str]]] = []
        for slot_name, slot in slots.items():
            if slot.stack != item_stacks[sid]:
                continue
            score, blocked, reasons = compute_slot_score(
                traits, slot, trait_defs, trait_sources_by_item[sid]
            )
            if blocked:
                continue
            valid.append((slot_name, score, reasons))
        if not valid:
            print(
                f"plan: stack item '{sid}' is blocked from every slot.",
                file=sys.stderr,
            )
            return 1
        valid.sort(key=lambda c: -c[1])
        candidates[sid] = valid

    slot_names = list(slots)
    slot_order = {slot_name: index for index, slot_name in enumerate(slot_names)}
    active_order = list(active)
    sorted_items = sorted(
        active,
        key=lambda item: (
            len(candidates[item]),
            -max(score for _slot_name, score, _reasons in candidates[item]),
            active_order.index(item),
        ),
    )
    candidate_scores = {
        item: {slot_name: score for slot_name, score, _reasons in item_candidates}
        for item, item_candidates in candidates.items()
    }
    remaining_max_scores: list[int] = [0] * (len(sorted_items) + 1)
    for index in range(len(sorted_items) - 1, -1, -1):
        item = sorted_items[index]
        remaining_max_scores[index] = remaining_max_scores[index + 1] + max(
            candidate_scores[item].values()
        )

    assignment: dict[str, str] = {}
    slot_traits: dict[str, list[set[str]]] = {slot_name: [] for slot_name in slots}
    slot_items: dict[str, list[str]] = {slot_name: [] for slot_name in slots}
    slot_counts: dict[str, int] = {slot_name: 0 for slot_name in slots}
    best_assignment: dict[str, str] | None = None
    best_key: tuple[int, ...] | None = None
    best_metrics: tuple[float, int, int, float] | None = None

    def assignment_tie_key(candidate_assignment: dict[str, str]) -> tuple[int, ...]:
        return tuple(slot_order[candidate_assignment[item]] for item in active_order)

    def balance_lower_bound(search_index: int) -> float:
        relaxed_counts = dict(slot_counts)
        remaining_by_stack: dict[str, int] = {}
        for item in sorted_items[search_index:]:
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

    def evaluate_complete(slot_score_total: int) -> tuple[float, int, int, float]:
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

    def seed_with_greedy_assignment() -> None:
        nonlocal best_assignment, best_key, best_metrics

        greedy_assignment: dict[str, str] = {}
        greedy_slot_traits: dict[str, list[set[str]]] = {
            slot_name: [] for slot_name in slots
        }
        greedy_slot_items: dict[str, list[str]] = {slot_name: [] for slot_name in slots}
        greedy_slot_counts: dict[str, int] = {slot_name: 0 for slot_name in slots}
        greedy_slot_score = 0
        for item in sorted_items:
            traits = active[item]
            chosen: tuple[str, int] | None = None
            for slot_name, score, _reasons in sorted(
                candidates[item],
                key=lambda candidate: (-candidate[1], slot_order[candidate[0]]),
            ):
                if _slot_is_blocked(
                    item, slot_name, traits,
                    greedy_slot_traits, greedy_slot_items,
                    active_components, substances, trait_defs, global_relations,
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

        prefer_with_bonus = 0
        for pair in prefer_pairs:
            a, b = tuple(pair)
            if greedy_assignment.get(a) == greedy_assignment.get(b):
                prefer_with_bonus += PREFER_WITH_BONUS
        balance_penalty = BALANCE_WEIGHT * sum(
            count * count for count in greedy_slot_counts.values()
        )
        total = greedy_slot_score + prefer_with_bonus - balance_penalty
        best_assignment = greedy_assignment
        best_metrics = (
            total,
            greedy_slot_score,
            prefer_with_bonus,
            balance_penalty,
        )
        best_key = assignment_tie_key(greedy_assignment)

    def search(index: int, slot_score_total: int) -> None:
        nonlocal best_assignment, best_key, best_metrics

        if best_metrics is not None:
            optimistic_total = (
                slot_score_total
                + remaining_max_scores[index]
                + len(prefer_pairs) * PREFER_WITH_BONUS
                - balance_lower_bound(index)
            )
            if optimistic_total < best_metrics[0] - 1e-9:
                return

        if index == len(sorted_items):
            metrics = evaluate_complete(slot_score_total)
            candidate_key = assignment_tie_key(assignment)
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

        item = sorted_items[index]
        traits = active[item]
        ordered_candidates = sorted(
            candidates[item],
            key=lambda candidate: (-candidate[1], slot_order[candidate[0]]),
        )
        for slot_name, score, _reasons in ordered_candidates:
            if _slot_is_blocked(
                item, slot_name, traits,
                slot_traits, slot_items,
                active_components, substances, trait_defs, global_relations,
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

    seed_with_greedy_assignment()
    search(0, 0)

    if best_assignment is None or best_metrics is None:
        print(
            "plan: no valid global assignment under slot conflict constraints.",
            file=sys.stderr,
        )
        return 1

    assignment = best_assignment
    _final_total, _slot_score_sum, prefer_bonus, _balance_pen = best_metrics

    schedule = _build_schedule_output(
        assignment=assignment,
        best_metrics=best_metrics,
        slots=slots,
        active_order=active_order,
        active_components=active_components,
        item_products=item_products,
        products=products,
        substances=substances,
        relations=global_relations,
        trait_defs=trait_defs,
        prefer_pairs=prefer_pairs,
        substance_to_active_items=substance_to_active_items,
        stack_entries=stack_entries,
        dashboard_files=dashboard_files,
        intra_product_conflicts_by_item=intra_product_conflicts_by_item,
        intra_product_relation_conflicts_by_item=intra_product_relation_conflicts_by_item,
        trait_sources_by_item=trait_sources_by_item,
        active=active,
        pillboxes=pillboxes,
        warnings_prefix=ambiguous_prefer_with_warnings,
    )

    SCHEDULE_PATH.write_text(dump_schedule_yaml(schedule))

    slot_loads = {
        f"{pillbox_name}.{slot_name}": len(slot_entry["products"])
        for pillbox_name, pillbox in schedule["pillboxes"].items()
        for slot_name, slot_entry in pillbox["slots"].items()
    }
    print(f"\nschedule written to {SCHEDULE_PATH}")
    print(f"slot loads: {slot_loads}")
    print(
        f"kept_together pairs: {len(prefer_pairs)} declared, "
        f"{prefer_bonus // PREFER_WITH_BONUS} together"
    )
    print(f"warnings: {len(schedule['warnings'])}")
    return 0
