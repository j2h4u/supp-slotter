"""Scheduling engine: cmd_* CLI handlers and their internal helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from planner.cards import (
    build_action_points,
    build_dashboard_review,
    build_empty_schedule_pillboxes,
    build_placement_notes,
    build_review_contexts,
    build_schedule_summary,
    check_dashboards,
    check_global_relations,
    check_pillbox_slot_ids,
    check_product_formulas,
    check_substances,
    check_traits,
    collect_active_unmatched_concerns,
    collect_dashboard_substance_refs,
    collect_intra_product_relation_conflicts,
    collect_missing_balance_relations,
    collect_missing_support_relations,
    collect_product_substance_refs,
    collect_similar_substances,
    component_sets_have_relation,
    derive_slot_fields,
    flatten_pillbox_slots,
    flatten_trait_defs,
    format_find_result,
    format_item_product_name,
    format_product_name,
    format_relation_warning,
    format_substance_name,
    find_product_results,
    find_substance_results,
    global_relation_refs,
    grouped_trait_defs,
    humanize_warning,
    is_generic_manual_review_warning,
    load_global_relations,
    load_product,
    load_product_registry,
    load_substance,
    load_substance_registry,
    normalize_stack_entries,
    print_central_relation_matches,
    print_trait_details,
    product_component_substances,
    readable_traits,
    validate_stacks,
)
from planner.io import (
    BALANCE_WEIGHT,
    DASHBOARDS_DIR,
    DATA_DIR,
    LEVEL_SCORES,
    PREFER_WITH_BONUS,
    PRODUCTS_DIR,
    RELATIONS_PATH,
    ROOT,
    SCHEDULE_PATH,
    STACKS_PATH,
    SUBSTANCES_DIR,
    display_message,
    display_path,
    dump_schedule_yaml,
    load_yaml,
    report,
    schema_errors,
    validate_schemas,
)
from planner.maintenance import run_auto_maintenance


def collect_orphans() -> dict[str, list[str]]:
    substance_files = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    product_files = sorted(PRODUCTS_DIR.glob("*.yaml"))
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []

    substances: dict[str, dict] = {}
    for sf in substance_files:
        substance, err = load_substance(sf)
        if err:
            continue
        substance_id = substance.get("id")
        if isinstance(substance_id, str):
            substances[substance_id] = substance

    products: dict[str, dict] = {}
    product_substance_refs: set[str] = set()
    for pf in product_files:
        product, err = load_product(pf)
        if err:
            continue
        product_id = product.get("id")
        if isinstance(product_id, str):
            products[product_id] = product
        for component in product.get("components") or []:
            if not isinstance(component, dict):
                continue
            substance_id = component.get("substance")
            if isinstance(substance_id, str):
                product_substance_refs.add(substance_id)

    prefer_with_refs: set[str] = set()
    relation_refs: set[str] = set()
    trait_refs: set[str] = set()
    for substance_id, substance in substances.items():
        if substance.get("prefer_with"):
            prefer_with_refs.add(substance_id)
        for target_id in substance.get("prefer_with") or []:
            if isinstance(target_id, str):
                prefer_with_refs.add(target_id)
        for trait_id in substance.get("traits") or []:
            if isinstance(trait_id, str):
                trait_refs.add(trait_id)
    relation_refs.update(global_relation_refs(substances, load_global_relations()))

    traits_data = load_yaml(DATA_DIR / "traits.yaml")
    traits = flatten_trait_defs(traits_data) if isinstance(traits_data, dict) else {}
    for trait in traits.values():
        if not isinstance(trait, dict):
            continue
        for target_id in trait.get("separate_from") or []:
            if isinstance(target_id, str):
                trait_refs.add(target_id)

    stacks_data = load_yaml(STACKS_PATH)
    stack_entries = (
        normalize_stack_entries(stacks_data)
        if isinstance(stacks_data, dict)
        else {}
    )
    stack_products = {
        entry["product"]
        for entry in stack_entries.values()
        if isinstance(entry, dict) and isinstance(entry.get("product"), str)
    }
    active_stack_products = {
        entry["product"]
        for entry in stack_entries.values()
        if (
            isinstance(entry, dict)
            and entry.get("stack") != "inactive"
            and isinstance(entry.get("product"), str)
        )
    }
    active_substances = collect_product_substance_refs(
        products, active_stack_products
    )
    stack_groups = stacks_data if isinstance(stacks_data, dict) else {}
    if not isinstance(stack_groups, dict):
        stack_groups = {}

    slots_data = load_yaml(DATA_DIR / "pillboxes.yaml")
    pillbox_stacks = set(slots_data) if isinstance(slots_data, dict) else set()

    substance_refs = (
        product_substance_refs
        | collect_dashboard_substance_refs(dashboard_files)
        | prefer_with_refs
        | relation_refs
    )
    unused_substances = sorted(set(substances) - substance_refs)
    products_without_stack = sorted(set(products) - stack_products)
    unused_traits = sorted(set(traits) - trait_refs)
    empty_stacks = sorted(
        stack
        for stack, items in stack_groups.items()
        if isinstance(items, list) and not items
    )
    stacks_without_pillboxes = sorted(
        set(stack_groups) - pillbox_stacks - {"inactive"}
    )
    pillboxes_without_stack = sorted(pillbox_stacks - set(stack_groups))

    return {
        "substances.unused": unused_substances,
        "products.without_stack": products_without_stack,
        "traits.unused": unused_traits,
        "stacks.empty": empty_stacks,
        "stacks.without_pillboxes": stacks_without_pillboxes,
        "pillboxes.without_stack": pillboxes_without_stack,
        "substances.similar_names": collect_similar_substances(substances),
        "relations.balance_missing": [
            format_relation_warning(warning)
            for warning in collect_missing_balance_relations(
                substances, active_substances, load_global_relations()
            )
        ],
        "relations.supports_missing": [
            format_relation_warning(warning)
            for warning in collect_missing_support_relations(
                substances, active_substances, load_global_relations()
            )
        ],
    }

def cmd_check() -> int:
    maintenance_result = run_auto_maintenance(quiet=True)
    if maintenance_result != 0:
        return maintenance_result

    errors: list[str] = []
    info: list[str] = []

    slots_path = DATA_DIR / "pillboxes.yaml"
    traits_path = DATA_DIR / "traits.yaml"

    for required in (slots_path, traits_path, RELATIONS_PATH):
        if not required.exists():
            return report([f"missing: {required}"], [])

    slots_data = load_yaml(slots_path)
    traits_data = load_yaml(traits_path)

    if not isinstance(slots_data, dict):
        return report([f"{slots_path}: top-level must be a mapping"], [])
    if not isinstance(traits_data, dict):
        return report([f"{traits_path}: top-level must be a mapping"], [])

    errors.extend(schema_errors(slots_data, "pillboxes", slots_path))
    errors.extend(schema_errors(traits_data, "traits", traits_path))

    if errors:
        return report(errors, info)

    errors.extend(check_pillbox_slot_ids(slots_data, slots_path))

    slot_fields = derive_slot_fields(slots_data)
    errors.extend(check_traits(traits_data, traits_path, slot_fields))

    trait_ids = set(flatten_trait_defs(traits_data).keys())

    all_substance_files = sorted(SUBSTANCES_DIR.glob("*.yaml"))
    s_errors, s_info, substance_ids = check_substances(all_substance_files, trait_ids)
    errors.extend(s_errors)
    info.extend(s_info)
    substances = load_substance_registry()
    relations_data = load_yaml(RELATIONS_PATH)
    errors.extend(check_global_relations(relations_data, substances))

    all_product_files = sorted(PRODUCTS_DIR.glob("*.yaml"))
    p_errors, p_info, product_ids = check_product_formulas(
        all_product_files, substance_ids
    )
    errors.extend(p_errors)
    info.extend(p_info)

    errors.extend(validate_stacks(STACKS_PATH, product_ids, trait_ids))
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []
    errors.extend(check_dashboards(dashboard_files, substance_ids))

    return report(errors, info)

def cmd_doctor() -> int:
    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    maintenance_result = run_auto_maintenance(quiet=True)
    if maintenance_result != 0:
        return maintenance_result

    sections = collect_orphans()

    print("Doctor / cleanup candidates")
    for section, items in sections.items():
        print(f"\n{section} ({len(items)})")
        if not items:
            print("  none")
            continue
        for item in items:
            print(f"  - {item}")
    return 0

def effective_stack_item_traits(
    product: dict,
    substances: dict[str, dict],
    traits_data: dict | None = None,
) -> tuple[set[str], dict[str, list[str]], list[dict]]:
    """Aggregate component substance traits for one physical stack item."""
    effective: set[str] = set()
    trait_sources: dict[str, list[str]] = {}
    trait_defs = flatten_trait_defs(traits_data) if isinstance(traits_data, dict) else {}

    for component_id in product_component_substances(product):
        substance = substances.get(component_id)
        if not substance:
            continue
        for trait_id in substance.get("traits") or []:
            effective.add(trait_id)
            trait_sources.setdefault(trait_id, [])
            if component_id not in trait_sources[trait_id]:
                trait_sources[trait_id].append(component_id)

    internal_conflicts: list[dict] = []
    if trait_defs:
        seen_conflict_pairs: set[frozenset[str]] = set()
        for left in sorted(effective):
            left_def = trait_defs.get(left) or {}
            for right in left_def.get("separate_from") or []:
                if right not in effective:
                    continue
                pair_key = frozenset([left, right])
                if pair_key in seen_conflict_pairs:
                    continue
                seen_conflict_pairs.add(pair_key)
                conflict = {
                    "type": "intra_product_trait_conflict",
                    "trait": left,
                    "conflicts_with": right,
                    "substances": list(trait_sources.get(left, [])),
                    "conflicting_substances": list(trait_sources.get(right, [])),
                }
                internal_conflicts.append(conflict)

    return effective, trait_sources, internal_conflicts

def print_find_section(
    title: str,
    results: list[tuple[float, str, str, Path]],
    limit: int,
) -> None:
    print(f"\n{title}")
    if not results:
        print("  none")
        return
    for score, card_id, label, path in results[:limit]:
        print(format_find_result(score, card_id, label, path))

def cmd_find(query_parts: list[str], limit: int) -> int:
    query = " ".join(part.strip() for part in query_parts if part.strip())
    if not query:
        print("find: query must not be empty", file=sys.stderr)
        return 1

    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    maintenance_result = run_auto_maintenance(quiet=True)
    if maintenance_result != 0:
        return maintenance_result

    print(f"Search results for: {query}")
    print_find_section("Substances", find_substance_results(query), limit)
    print_find_section("Products", find_product_results(query), limit)
    return 0

def cmd_review_substance(target: str) -> int:
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / path

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        print(f"{display_path(path)}: file not found", file=sys.stderr)
        return 1

    substances_root = SUBSTANCES_DIR.resolve()
    try:
        resolved.relative_to(substances_root)
    except ValueError:
        print(
            f"{display_path(path)}: review-substance only accepts paths inside {display_path(SUBSTANCES_DIR)}/",
            file=sys.stderr,
        )
        return 1

    if resolved.suffix != ".yaml":
        print(
            f"{display_path(path)}: review-substance only accepts .yaml files",
            file=sys.stderr,
        )
        return 1

    schema_result = validate_schemas()
    if schema_result != 0:
        return schema_result

    path = resolved
    substance, err = load_substance(path)
    if err is not None:
        print(display_message(err), file=sys.stderr)
        return 1
    if substance is None:
        print(f"{display_path(path)}: substance could not be loaded", file=sys.stderr)
        return 1

    traits_data = load_yaml(DATA_DIR / "traits.yaml")
    if not isinstance(traits_data, dict):
        print("data/traits.yaml: top-level must be a mapping", file=sys.stderr)
        return 1
    trait_defs = flatten_trait_defs(traits_data)
    if not trait_defs:
        print("data/traits.yaml: no traits found", file=sys.stderr)
        return 1

    current_traits = {
        trait
        for trait in substance.get("traits") or []
        if isinstance(trait, str)
    }
    aliases = substance.get("aliases") or []
    concerns = substance.get("unmatched_concerns") or []

    print(f"Substance review: {format_substance_name(substance)}")
    print(f"File: {display_path(path)}")
    if substance.get("id"):
        print(f"ID: {substance['id']}")
    if aliases:
        print("Aliases: " + ", ".join(str(alias) for alias in aliases))
    print_central_relation_matches(substance, load_substance_registry())
    print()
    print("Before editing traits, scan this checklist and mark only source-backed facts.")
    print("If a fact matters but no trait fits, use unmatched_concerns.")
    print("Put substance-to-substance relations in data/relations.yaml, not in this card.")
    print()
    print("Traits")
    for namespace, entries in grouped_trait_defs(trait_defs).items():
        print(f"\n{namespace}")
        for short_name, trait_id, trait in entries:
            marker = "x" if trait_id in current_traits else " "
            label = trait.get("label")
            label_text = f" - {label}" if label else ""
            print(f"  [{marker}] {short_name}{label_text}")
            print_trait_details(trait)

    unknown_traits = sorted(current_traits - set(trait_defs), key=str.casefold)
    if unknown_traits:
        print("\nunknown")
        for trait_id in unknown_traits:
            print(f"  [x] {trait_id}")

    print("\nUnmatched concerns")
    if concerns:
        for concern in concerns:
            print(f"  - {concern}")
    else:
        print("  none")

    return 0

def explain_slot_choice(
    trait_ids: set[str],
    slot: dict,
    traits_data: dict,
) -> list[str]:
    notes: list[str] = []
    trait_defs = flatten_trait_defs(traits_data) if isinstance(traits_data, dict) else {}
    for trait_id in sorted(trait_ids):
        trait = trait_defs.get(trait_id)
        if not isinstance(trait, dict):
            continue
        label = str(trait.get("label") or trait_id)
        has_positive_preference = False
        positive_preference_matched = False
        tradeoff_matched = False
        for effect in trait.get("effects") or []:
            if not isinstance(effect, dict):
                continue
            level = effect.get("level")
            if level in {"prefer", "prefer_strong"}:
                has_positive_preference = True
            match = effect.get("match") or {}
            if not isinstance(match, dict) or not slot_matches(slot, match):
                continue
            if effect.get("block") is True:
                notes.append(f"{label}: blocked incompatible slots.")
            elif level in {"avoid", "avoid_strong"}:
                tradeoff_matched = True
                notes.append(f"{label}: tradeoff; this slot is not ideal for that preference.")
            elif level in {"prefer", "prefer_strong"}:
                positive_preference_matched = True
                notes.append(f"{label}: fits this slot.")
        if has_positive_preference and not positive_preference_matched and not tradeoff_matched:
            notes.append(f"{label}: tradeoff; preferred slot condition was not available here.")
    return sorted(set(notes), key=str.casefold) or [
        "No strict timing driver; placed in an available compatible slot."
    ]

def build_substance_slot_names(
    *,
    slot_items: list[str],
    item_products: dict[str, str],
    products: dict[str, dict],
    substances: dict[str, dict],
) -> list[str]:
    names: set[str] = set()
    for item_id in slot_items:
        product_id = item_products[item_id]
        product = products[product_id]
        for component in product.get("components") or []:
            if not isinstance(component, dict):
                continue
            substance_id = component.get("substance")
            if not isinstance(substance_id, str):
                continue
            substance = substances.get(substance_id) or {}
            names.add(format_substance_name(substance))
    return sorted(names, key=str.casefold)

def slot_matches(slot: dict, match_pattern: dict) -> bool:
    """AND-only: slot satisfies match if all listed fields equal."""
    for key, value in match_pattern.items():
        if slot.get(key) != value:
            return False
    return True

def compute_slot_score(
    trait_ids: set[str],
    slot: dict,
    traits_data: dict,
    trait_sources: dict[str, list[str]] | None = None,
) -> tuple[int, bool, list[str]]:
    """Returns (score, blocked, reasons)."""
    score = 0
    blocked = False
    reasons: list[str] = []
    trait_defs = flatten_trait_defs(traits_data)
    for trait_id in sorted(trait_ids):
        trait = trait_defs.get(trait_id)
        if not trait:
            continue
        for eff in trait.get("effects") or []:
            match_pattern = eff.get("match", {})
            if not slot_matches(slot, match_pattern):
                continue
            source_text = ""
            if trait_sources is not None:
                sources = trait_sources.get(trait_id) or ["unknown"]
                source_text = f" from {', '.join(sources)}"
            if eff.get("block") is True:
                blocked = True
                reasons.append(f"{trait_id}{source_text} BLOCK on match {match_pattern}")
            elif "level" in eff:
                level = eff["level"]
                delta = LEVEL_SCORES.get(level, 0)
                score += delta
                reasons.append(
                    f"{trait_id}{source_text} match {match_pattern} -> "
                    f"{level} ({delta:+d})"
                )
    return score, blocked, reasons

def must_separate(t1: set[str], t2: set[str], traits_data: dict) -> bool:
    """Symmetric: t1 and t2 share a slot conflict if either declares separate_from
    referencing a trait in the other."""
    trait_defs = flatten_trait_defs(traits_data)

    def declares_against(traits_a: set[str], traits_b: set[str]) -> bool:
        for trait_id in traits_a:
            trait = trait_defs.get(trait_id)
            if not trait:
                continue
            for sep in trait.get("separate_from") or []:
                if sep in traits_b:
                    return True
        return False

    return declares_against(t1, t2) or declares_against(t2, t1)

def cmd_plan() -> int:
    # Implicit check first
    print("=== running check ===", file=sys.stderr)
    check_result = cmd_check()
    if check_result != 0:
        print("plan aborted: check failed; fix errors above and retry.", file=sys.stderr)
        return check_result
    print("=== check passed; building schedule ===", file=sys.stderr)

    slots_data = load_yaml(DATA_DIR / "pillboxes.yaml")
    traits_data = load_yaml(DATA_DIR / "traits.yaml")
    stacks_data = load_yaml(STACKS_PATH)

    if not (
        isinstance(slots_data, dict)
        and isinstance(traits_data, dict)
        and isinstance(stacks_data, dict)
    ):
        print("plan: data file not a mapping", file=sys.stderr)
        return 1

    slots: dict[str, dict] = dict(
        sorted(
            flatten_pillbox_slots(slots_data).items(),
            key=lambda kv: (
                kv[1].get("pillbox", ""),
                kv[1].get("order", 0),
            ),
        )
    )

    substances = load_substance_registry()
    products = load_product_registry()
    global_relations = load_global_relations()
    dashboard_files = sorted(DASHBOARDS_DIR.glob("*.yaml")) if DASHBOARDS_DIR.exists() else []
    stack_entries = normalize_stack_entries(stacks_data)

    # Non-inactive stack items + effective traits aggregated from product components
    active: dict[str, set[str]] = {}
    item_products: dict[str, str] = {}
    active_components: dict[str, list[str]] = {}
    trait_sources_by_item: dict[str, dict[str, list[str]]] = {}
    intra_product_conflicts_by_item: dict[str, list[dict]] = {}
    intra_product_relation_conflicts_by_item: dict[str, list[dict]] = {}
    item_stacks: dict[str, str] = {}
    for item_id, entry in stack_entries.items():
        stack = entry.get("stack")
        if stack == "inactive":
            continue
        product_id = entry.get("product")
        product = products.get(product_id)
        if not product:
            print(
                f"plan: skipping '{item_id}' — product '{product_id}' missing or invalid",
                file=sys.stderr,
            )
            continue
        effective, trait_sources, internal_conflicts = effective_stack_item_traits(
            product, substances, traits_data
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
        item_stacks[item_id] = stack

    if not active:
        print("plan: no non-inactive stack items.", file=sys.stderr)
        return 1

    workout_stacks = {
        slot.get("stack")
        for slot in slots.values()
        if str(slot.get("near", "")).startswith("workout_")
        and isinstance(slot.get("stack"), str)
    }
    for item_id, traits in active.items():
        activity_traits = sorted(trait for trait in traits if trait.startswith("activity:"))
        if activity_traits and item_stacks[item_id] not in workout_stacks:
            print(
                f"plan: stack item '{item_id}' has {', '.join(activity_traits)} "
                f"but stack '{item_stacks[item_id]}' has no workout pillbox slots.",
                file=sys.stderr,
            )
            return 1

    # Symmetric prefer_with pairs between schedulable product-backed stack items.
    prefer_pairs: set[frozenset[str]] = set()
    ambiguous_prefer_with_warnings: list[dict] = []
    substance_to_active_items: dict[str, list[str]] = {}
    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance_to_active_items.setdefault(component_id, []).append(item_id)
    for component_id in substance_to_active_items:
        substance_to_active_items[component_id].sort()

    for item_id, component_ids in active_components.items():
        for component_id in component_ids:
            substance = substances.get(component_id) or {}
            for target_substance in substance.get("prefer_with") or []:
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

    # Candidate slots per stack item: list of (slot_name, score, reasons)
    candidates: dict[str, list[tuple[str, int, list[str]]]] = {}
    for sid, traits in active.items():
        valid: list[tuple[str, int, list[str]]] = []
        for slot_name, slot in slots.items():
            if slot.get("stack") != item_stacks[sid]:
                continue
            score, blocked, reasons = compute_slot_score(
                traits, slot, traits_data, trait_sources_by_item[sid]
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
        valid.sort(key=lambda c: -c[1])  # best score first
        candidates[sid] = valid

    # === Exhaustive global search over the small candidate space ===
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
                if slot.get("stack") == stack
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
                if any(
                    must_separate(traits, existing_traits, traits_data)
                    for existing_traits in greedy_slot_traits[slot_name]
                ):
                    continue
                if any(
                    component_sets_have_relation(
                        active_components[item],
                        active_components[existing_item],
                        substances,
                        "competes",
                        global_relations,
                    )
                    for existing_item in greedy_slot_items[slot_name]
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
            if any(
                must_separate(traits, existing_traits, traits_data)
                for existing_traits in slot_traits[slot_name]
            ):
                continue
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

    # Build schedule.yaml
    schedule: dict = {
        "summary": {},
        "action_points": [],
        "review_contexts": [],
        "placement_notes": [],
        "pillboxes": build_empty_schedule_pillboxes(slots_data),
        "benefits": [],
        "risks": [],
        "warnings": [],
        "kept_together": [
            {
                "pair": sorted([
                    format_item_product_name(item_id, item_products, products)
                    for item_id in sorted(p)
                ], key=str.casefold),
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
        pillbox_name = str(slots[slot_name].get("pillbox"))
        schedule["pillboxes"][pillbox_name]["slots"][slot_name]["products"].append(
            format_item_product_name(sid, item_products, products)
        )
    for pillbox in schedule["pillboxes"].values():
        for slot_entry in pillbox["slots"].values():
            slot_entry["products"] = sorted(slot_entry["products"], key=str.casefold)

    for slot_name, slot in slots.items():
        pillbox_name = str(slot.get("pillbox"))
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
        if (
            isinstance(entry, dict)
            and entry.get("stack") == "inactive"
            and isinstance(entry.get("product"), str)
        )
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
        schedule["explanations"][product_name] = {
            "components": [
                format_substance_name(substances.get(substance_id) or {"id": substance_id})
                for substance_id in active_components[sid]
            ],
            "pillbox": slot.get("pillbox"),
            "slot": slot_name,
            "why_here": explain_slot_choice(active[sid], slot, traits_data),
            "review_tags": readable_traits(active[sid], traits_data),
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
    for sid, internal_conflicts in intra_product_relation_conflicts_by_item.items():
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
    schedule["warnings"].extend(ambiguous_prefer_with_warnings)

    for sid, traits in active.items():
        for trait_id in sorted(traits):
            trait_def = flatten_trait_defs(traits_data).get(trait_id)
            if trait_def and trait_def.get("warning"):
                for source in trait_sources_by_item[sid].get(trait_id) or ["unknown"]:
                    schedule["warnings"].append(
                        {
                            "item": sid,
                            "product": item_products[sid],
                            "substance": source,
                            "trait": trait_id,
                            "message": trait_def.get(
                                "description", "Manual review required."
                            ),
                            "action": trait_def.get("action", ""),
                        }
                    )

    for warning in collect_missing_balance_relations(
        substances, active_substance_ids, global_relations
    ):
        schedule["warnings"].append(warning)
    for warning in collect_missing_support_relations(
        substances, active_substance_ids, global_relations
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
