"""Slot-assignment helpers used by `cmd_plan` (private to the engine package)."""

from __future__ import annotations

from planner.cards import (
    flatten_trait_defs,
    format_substance_name,
    product_component_substances,
)
from planner.io import LEVEL_SCORES


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

