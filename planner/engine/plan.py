"""`plan` command: build schedule.yaml via slot-assignment search."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, NamedTuple, cast

from planner.cards.dashboards import build_dashboard_review
from planner.cards.fact_index import build_active_fact_index
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
from planner.cards.relations import load_global_relations
from planner.cards.relations_surreal import (
    SurrealSession,
    build_surreal_db,
    collect_antagonizing_relations,
    collect_intra_product_relation_conflicts,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    component_sets_have_relation,
)
from planner.cards.schedule import (
    build_placement_notes,
    build_schedule_summary,
)
from planner.cards.stacks import normalize_stack_entries
from planner.cards.substance import format_substance_name, load_substance_registry
from planner.cards.traits import load_traits, readable_traits
from planner.cards.warnings import (
    collect_active_safety_concerns,
    humanize_warning,
    is_generic_manual_review_warning,
)
from planner.contracts import CardLoadError, Pillbox, Product, Relation, Slot, Substance, TraitDef
from planner.engine._root_patch import maybe_patch_root
from planner.engine._scheduling import (
    build_substance_slot_names,
    compute_slot_score,
    effective_stack_item_traits,
    explain_slot_choice,
)
from planner.engine.check import cmd_check
from planner.engine.results import PlanResult
from planner.io import (
    BALANCE_WEIGHT,
    DASHBOARDS_DIR,
    DATA_DIR,
    PREFER_WITH_BONUS,
    SCHEDULE_PATH,
    SECONDARY_TRAIT_WEIGHT,
    STACKS_PATH,
    dump_schedule_yaml,
    load_yaml,
)


class PlanInputs(NamedTuple):
    slots: dict[str, Slot]
    trait_defs: dict[str, TraitDef]
    substances: dict[str, Substance]
    products: dict[str, Product]
    global_relations: list[Relation]
    dashboard_files: list[Path]
    stack_entries: dict[str, Any]
    pillboxes: dict[str, Pillbox]


class ActiveIndex(NamedTuple):
    item_traits: dict[str, set[str]]
    secondary_traits_by_item: dict[str, set[str]]
    item_products: dict[str, str]
    active_components: dict[str, list[str]]
    trait_sources_by_item: dict[str, dict[str, list[str]]]
    intra_product_conflicts_by_item: dict[str, list[dict[str, Any]]]
    intra_product_relation_conflicts_by_item: dict[str, list[dict[str, Any]]]
    item_stacks: dict[str, str]


def _load_plan_inputs(
    data_dir: Path,
) -> PlanInputs | None:
    """Load all static inputs needed before the active-index build.

    Returns a PlanInputs or None on failure.
    """
    try:
        pillboxes = load_pillboxes(data_dir / "pillboxes.yaml")
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
    try:
        trait_defs = load_traits(data_dir / "traits.yaml")
    except CardLoadError as e:
        print(f"plan: {e.message}", file=sys.stderr)
        return None
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

    return PlanInputs(
        slots=slots,
        trait_defs=trait_defs,
        substances=substances,
        products=products,
        global_relations=global_relations,
        dashboard_files=dashboard_files,
        stack_entries=stack_entries,
        pillboxes=pillboxes,
    )


def _build_active_index(
    stack_entries: dict[str, Any],
    products: dict[str, Any],
    substances: dict[str, Any],
    trait_defs: dict[str, Any],
    global_relations: list[Relation],
    slots: dict[str, Slot],
    errors: list[str],
    db: SurrealSession,
) -> ActiveIndex | None:
    """Build per-item trait/conflict/stack indexes from the active stack entries.

    Returns an ActiveIndex or None if any early-exit condition is hit.
    Appends human-readable error messages to *errors* before returning None.
    """
    item_traits: dict[str, set[str]] = {}
    secondary_traits_by_item: dict[str, set[str]] = {}
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
        effective, _primary_traits, secondary_only_traits, trait_sources, internal_conflicts = (
            effective_stack_item_traits(product, substances, trait_defs)
        )
        item_traits[item_id] = effective
        secondary_traits_by_item[item_id] = secondary_only_traits
        item_products[item_id] = product_id
        active_components[item_id] = product_component_substances(product)
        trait_sources_by_item[item_id] = trait_sources
        intra_product_conflicts_by_item[item_id] = internal_conflicts
        intra_product_relation_conflicts_by_item[item_id] = (
            collect_intra_product_relation_conflicts(
                db,
                item_id=item_id,
                product_id=product_id,
                component_ids=active_components[item_id],
                relation_type="competes",
            )
        )
        item_stacks[item_id] = stack if isinstance(stack, str) else ""

    if not item_traits:
        msg = "plan: no non-inactive stack items."
        print(msg, file=sys.stderr)
        errors.append(msg)
        return None

    workout_stacks = {
        slot.stack
        for slot in slots.values()
        if slot.near.startswith("workout_")
    }
    for item_id, traits in item_traits.items():
        activity_traits = sorted(trait for trait in traits if trait.startswith("activity:"))
        if activity_traits and item_stacks[item_id] not in workout_stacks:
            msg = (
                f"plan: stack item '{item_id}' has {', '.join(activity_traits)} "
                f"but stack '{item_stacks[item_id]}' has no workout pillbox slots."
            )
            print(msg, file=sys.stderr)
            errors.append(msg)
            return None

    return ActiveIndex(
        item_traits=item_traits,
        secondary_traits_by_item=secondary_traits_by_item,
        item_products=item_products,
        active_components=active_components,
        trait_sources_by_item=trait_sources_by_item,
        intra_product_conflicts_by_item=intra_product_conflicts_by_item,
        intra_product_relation_conflicts_by_item=intra_product_relation_conflicts_by_item,
        item_stacks=item_stacks,
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
    active: ActiveIndex,
    item_id_sequence: list[str],
    products: dict[str, Any],
    substances: dict[str, Any],
    relations: list[Relation],
    trait_defs: dict[str, Any],
    prefer_pairs: set[frozenset[str]],
    substance_to_active_items: dict[str, list[str]],
    stack_entries: dict[str, Any],
    dashboard_files: list[Any],
    pillboxes: Any,
    warnings_prefix: list[dict[str, Any]],
    db: SurrealSession,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the complete schedule dict from a solved assignment.

    Returns the schedule dict ready to be serialised (excluding the write step).
    """
    schedule: dict[str, Any] = {
        "summary": {},
        "placement_notes": [],
        "pillboxes": build_empty_schedule_pillboxes(pillboxes),
        "benefits": [],
        "risks": [],
        "warnings": [],
        "kept_together": [
            {
                "pair": sorted(
                    [
                        format_item_product_name(item_id, active.item_products, products)
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

    for sid in item_id_sequence:
        slot_name = assignment[sid]
        pillbox_name = slots[slot_name].pillbox
        schedule["pillboxes"][pillbox_name]["slots"][slot_name]["products"].append(
            format_item_product_name(sid, active.item_products, products)
        )
    for pillbox in schedule["pillboxes"].values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"] = sorted(slot_entry["products"], key=str.casefold)

    for slot_name, slot in slots.items():
        pillbox_name = slot.pillbox
        slot_entry = schedule["pillboxes"][pillbox_name]["slots"][slot_name]
        slot_item_ids = [
            item_id for item_id in item_id_sequence if assignment[item_id] == slot_name
        ]
        slot_entry["substances"] = build_substance_slot_names(
            assigned_item_ids=slot_item_ids,
            item_products=active.item_products,
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
    schedule["active_fact_index"] = build_active_fact_index(
        item_id_sequence=item_id_sequence,
        item_products=active.item_products,
        products=products,
        substances=substances,
        trait_defs=trait_defs,
        dashboard_files=dashboard_files,
    )

    for sid in item_id_sequence:
        slot_name = assignment[sid]
        slot = slots[slot_name]
        product_name = format_item_product_name(sid, active.item_products, products)
        components_list: list[str] = []
        for substance_id in active.active_components[sid]:
            substance_dc = substances.get(substance_id)
            if substance_dc is not None:
                components_list.append(format_substance_name(substance_dc))
            else:
                components_list.append(substance_id)
        schedule["explanations"][product_name] = {
            "components": components_list,
            "pillbox": slot.pillbox,
            "slot": slot_name,
            "why_here": explain_slot_choice(active.item_traits[sid], slot, trait_defs),
            "review_tags": readable_traits(active.item_traits[sid], trait_defs),
        }

    for sid, internal_conflicts in active.intra_product_conflicts_by_item.items():
        for conflict in internal_conflicts:
            schedule["warnings"].append(
                {
                    "type": "intra_product_trait_conflict",
                    "item": sid,
                    "product": active.item_products[sid],
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
    for _sid, internal_conflicts in active.intra_product_relation_conflicts_by_item.items():
        for conflict in internal_conflicts:
            schedule["warnings"].append(conflict)

    schedule["warnings"].extend(
        collect_active_safety_concerns(
            active_order=item_id_sequence,
            active_components=active.active_components,
            item_products=active.item_products,
            products=products,
            substances=substances,
        )
    )
    schedule["warnings"].extend(warnings_prefix)

    for sid, traits in active.item_traits.items():
        for trait_id in sorted(traits):
            trait_def = trait_defs.get(trait_id)
            if trait_def is not None and trait_def.warning:
                for source in active.trait_sources_by_item[sid].get(trait_id) or ["unknown"]:
                    schedule["warnings"].append(
                        {
                            "item": sid,
                            "product": active.item_products[sid],
                            "substance": source,
                            "trait": trait_id,
                            "message": trait_def.description or "Manual review required.",
                            "action": trait_def.action or "",
                        }
                    )

    for warning in collect_missing_balance_relations(db, active_substance_ids):
        schedule["warnings"].append(warning)
    for warning in collect_missing_support_relations(db, active_substance_ids):
        schedule["warnings"].append(warning)
    for warning in collect_antagonizing_relations(db, active_substance_ids):
        schedule["warnings"].append(warning)

    raw_warnings = list(schedule["warnings"])
    schedule["warnings"] = [
        humanize_warning(warning, products=products, substances=substances)
        for warning in schedule["warnings"]
        if not is_generic_manual_review_warning(warning)
    ]
    schedule["placement_notes"] = build_placement_notes(schedule)
    schedule["summary"] = build_schedule_summary(schedule)

    return schedule, raw_warnings


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


def _run_plan_search(
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
    db: SurrealSession,
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
                if _slot_is_blocked(
                    item, slot_name, traits,
                    greedy_slot_traits, greedy_slot_items,
                    active_components, substances, trait_defs, global_relations,
                    db,
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
            if _slot_is_blocked(
                item, slot_name, traits,
                slot_traits, slot_items,
                active_components, substances, trait_defs, global_relations,
                db,
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
    db: SurrealSession,
) -> bool:
    """Return True if item cannot be placed in slot_name due to substance-level competes
    (relations.yaml) or class-level competes (relations.yaml, source_class/target_class).
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
    # Substance-level competes (unchanged path).
    if any(
        component_sets_have_relation(
            db,
            active_components[item],
            active_components[existing_item],
            "competes",
        )
        for existing_item in slot_items[slot_name]
    ):
        return True
    return False


def cmd_plan(data_root: Path | None = None) -> PlanResult:
    """Build schedule.yaml via slot-assignment search; returns a PlanResult with raw warning dicts."""
    with maybe_patch_root(data_root):
        return _cmd_plan_inner()


def _cmd_plan_inner() -> PlanResult:
    errors: list[str] = []
    print("=== running check ===")
    check_result = cmd_check()
    if check_result.exit_code != 0:
        print("plan: skipped (check failed; see errors above)", file=sys.stderr)
        return PlanResult(
            exit_code=check_result.exit_code,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=list(check_result.errors),
        )
    print("=== check passed; building schedule ===")

    inputs = _load_plan_inputs(DATA_DIR)
    if inputs is None:
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=errors,
        )
    slots = inputs.slots
    substances = inputs.substances
    products = inputs.products
    trait_defs = inputs.trait_defs

    db = build_surreal_db(
        inputs.substances, inputs.global_relations, inputs.products,
    )

    active = _build_active_index(
        inputs.stack_entries, inputs.products, inputs.substances,
        inputs.trait_defs, inputs.global_relations, inputs.slots,
        errors=errors,
        db=db,
    )
    if active is None:
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=errors,
        )

    prefer_pairs, ambiguous_prefer_with_warnings, substance_to_active_items = (
        _resolve_prefer_pairs(active.active_components, active.item_products, substances)
    )

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
            return PlanResult(
                exit_code=1,
                schedule_written=False,
                warnings=[],
                slot_loads={},
                prefer_pairs_declared=0,
                prefer_pairs_together=0,
                errors=errors,
            )
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

    best_assignment, best_metrics = _run_plan_search(
        slots=slots,
        items_by_scheduling_priority=items_by_scheduling_priority,
        item_id_sequence=item_id_sequence,
        item_traits=active.item_traits,
        item_stacks=active.item_stacks,
        feasible_slots_by_item=feasible_slots_by_item,
        slot_score_lookup=slot_score_lookup,
        remaining_score_upper_bound=remaining_score_upper_bound,
        prefer_pairs=prefer_pairs,
        active_components=active.active_components,
        substances=substances,
        trait_defs=trait_defs,
        global_relations=inputs.global_relations,
        db=db,
    )

    if best_assignment is None or best_metrics is None:
        tight_items = [
            (item_id, [name for name, _score, _reasons in candidates])
            for item_id, candidates in sorted(feasible_slots_by_item.items())
            if len(candidates) <= 1
        ]
        if tight_items:
            header = "plan: items with ≤1 feasible slot (likely cause):"
            print(header, file=sys.stderr)
            errors.append(header)
            for item_id, slot_names in tight_items:
                slot_list = ", ".join(slot_names) if slot_names else "(none)"
                line = f"  - {item_id}: {slot_list}"
                print(line, file=sys.stderr)
                errors.append(line)
        no_assign_msg = "plan: no valid global assignment under slot conflict constraints."
        print(no_assign_msg, file=sys.stderr)
        errors.append(no_assign_msg)
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=[],
            slot_loads={},
            prefer_pairs_declared=0,
            prefer_pairs_together=0,
            errors=errors,
        )

    assignment = best_assignment
    _final_total, _slot_score_sum, prefer_bonus, _balance_penalty = best_metrics

    schedule, raw_warnings = _build_schedule_output(
        assignment=assignment,
        best_metrics=best_metrics,
        slots=slots,
        active=active,
        item_id_sequence=item_id_sequence,
        products=products,
        substances=substances,
        relations=inputs.global_relations,
        trait_defs=trait_defs,
        prefer_pairs=prefer_pairs,
        substance_to_active_items=substance_to_active_items,
        stack_entries=inputs.stack_entries,
        dashboard_files=inputs.dashboard_files,
        pillboxes=inputs.pillboxes,
        warnings_prefix=ambiguous_prefer_with_warnings,
        db=db,
    )

    schedule_written = False
    try:
        SCHEDULE_PATH.write_text(dump_schedule_yaml(schedule))
        schedule_written = True
    except OSError as e:
        msg = f"plan: failed to write {SCHEDULE_PATH}: {e}"
        print(msg, file=sys.stderr)
        errors.append(msg)
        return PlanResult(
            exit_code=1,
            schedule_written=False,
            warnings=raw_warnings,
            slot_loads={},
            prefer_pairs_declared=len(prefer_pairs),
            prefer_pairs_together=prefer_bonus // PREFER_WITH_BONUS,
            errors=errors,
        )

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
    return PlanResult(
        exit_code=0,
        schedule_written=schedule_written,
        warnings=raw_warnings,
        slot_loads=slot_loads,
        prefer_pairs_declared=len(prefer_pairs),
        prefer_pairs_together=prefer_bonus // PREFER_WITH_BONUS,
        errors=errors,
    )
