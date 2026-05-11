"""Slot-assignment helpers used by `cmd_plan` (private to the engine package)."""

from __future__ import annotations

from typing import Any

from planner.cards.substance import format_substance_name
from planner.contracts import Product, Slot, Substance, TraitDef, TraitEffect, TraitEffectMatch
from planner.io import LEVEL_SCORES


def effective_stack_item_traits(
    product: Product,
    substances: dict[str, Substance],
    trait_defs: dict[str, TraitDef],
) -> tuple[set[str], set[str], set[str], dict[str, list[str]], list[dict[str, Any]]]:
    """Aggregate component substance traits for one physical stack item.

    Returns a 5-tuple:
      effective_traits:      set[str]             — full union of all component trait IDs
                                                    (primary + secondary); unchanged semantics
      primary_traits:        set[str]             — union over components where primary is True
      secondary_only_traits: set[str]             — traits in the full union NOT in primary_traits;
                                                    a trait shared by a primary and a secondary
                                                    component is treated as primary
      trait_sources:         dict[str, list[str]] — maps each trait ID to the list of
                                                    component substance IDs that carry it
      internal_conflicts:    list[dict[str, Any]] — intra-product trait conflicts computed over
                                                    the full union (physical inseparability means
                                                    timing conflicts are real regardless of primacy)

    If no component has primary=True, all are treated as primary (backward
    compatible — full union scores at full weight, secondary_only_traits is empty).
    """
    effective: set[str] = set()
    primary_traits: set[str] = set()
    trait_sources: dict[str, list[str]] = {}

    # Infer primacy: if any component is explicitly marked primary=True, only
    # those components are primary; unmarked (None) components are secondary.
    # If no component is marked, all are primary (backward compat).
    has_explicit_primary = any(c.primary is True for c in product.components)

    for component in product.components:
        component_id = component.substance
        substance = substances.get(component_id)
        if substance is None:
            continue
        is_primary = (not has_explicit_primary) or (component.primary is True)
        # Build scheduling traits from the 5 scheduling-relevant namespaces only.
        # dashboard: is intentionally excluded — it's a curation marker with no slot effects.
        scheduling_traits = (
            {f"is:{s}" for s in substance.is_}
            | {f"intake:{s}" for s in substance.intake}
            | {f"effect:{s}" for s in substance.effect}
            | {f"risk:{s}" for s in substance.risk}
            | {f"activity:{s}" for s in substance.activity}
        )
        for trait_id in scheduling_traits:
            effective.add(trait_id)
            sources = trait_sources.setdefault(trait_id, [])
            if component_id not in sources:
                sources.append(component_id)
            if is_primary:
                primary_traits.add(trait_id)

    # A trait shared by a primary and a secondary component is treated as primary.
    secondary_only_traits = effective - primary_traits

    internal_conflicts: list[dict[str, Any]] = []
    seen_conflict_pairs: set[frozenset[str]] = set()
    for left in sorted(effective):
        left_def = trait_defs.get(left)
        if left_def is None:
            continue
        for right in left_def.separate_from:
            if right not in effective:
                continue
            pair_key = frozenset([left, right])
            if pair_key in seen_conflict_pairs:
                continue
            seen_conflict_pairs.add(pair_key)
            internal_conflicts.append(
                {
                    "type": "intra_product_trait_conflict",
                    "trait": left,
                    "conflicts_with": right,
                    "substances": list(trait_sources.get(left, [])),
                    "conflicting_substances": list(trait_sources.get(right, [])),
                }
            )

    return effective, primary_traits, secondary_only_traits, trait_sources, internal_conflicts


def slot_matches(slot: Slot, match: TraitEffectMatch) -> bool:
    if match.near is not None and slot.near != match.near:
        return False
    if match.food is not None and slot.food != match.food:
        return False
    return True


def _explain_effect_for_slot(label: str, effect: TraitEffect, slot: Slot) -> str | None:
    if not slot_matches(slot, effect.match):
        return None
    if effect.block is True:
        return f"{label}: blocked incompatible slots."
    if effect.level in {"avoid", "avoid_strong"}:
        return f"{label}: tradeoff; this slot is not ideal for that preference."
    if effect.level in {"prefer", "prefer_strong"}:
        return f"{label}: fits this slot."
    return None


def explain_slot_choice(
    trait_ids: set[str],
    slot: Slot,
    trait_defs: dict[str, TraitDef],
) -> list[str]:
    reasons: list[str] = []
    for trait_id in sorted(trait_ids):
        trait = trait_defs.get(trait_id)
        if trait is None:
            continue
        label = trait.label or trait_id
        has_positive_preference = False
        positive_preference_matched = False
        tradeoff_matched = False
        for effect in trait.effects:
            if effect.level in {"prefer", "prefer_strong"}:
                has_positive_preference = True
            note = _explain_effect_for_slot(label, effect, slot)
            if note is not None:
                if effect.level in {"avoid", "avoid_strong"}:
                    tradeoff_matched = True
                elif effect.level in {"prefer", "prefer_strong"}:
                    positive_preference_matched = True
                reasons.append(note)
        if has_positive_preference and not positive_preference_matched and not tradeoff_matched:
            reasons.append(f"{label}: tradeoff; preferred slot condition was not available here.")
    return sorted(set(reasons), key=str.casefold) or [
        "No strict timing driver; placed in an available compatible slot."
    ]


def build_substance_slot_names(
    *,
    assigned_item_ids: list[str],
    item_products: dict[str, str],
    products: dict[str, Product],
    substances: dict[str, Substance],
) -> list[str]:
    names: set[str] = set()
    for item_id in assigned_item_ids:
        product_id = item_products[item_id]
        product = products.get(product_id)
        if product is None:
            continue
        for component in product.components:
            substance = substances.get(component.substance)
            if substance is None:
                continue
            names.add(format_substance_name(substance))
    return sorted(names, key=str.casefold)


def _format_match_pattern(match: TraitEffectMatch) -> dict[str, Any]:
    pattern: dict[str, Any] = {}
    if match.near is not None:
        pattern["near"] = match.near
    if match.food is not None:
        pattern["food"] = match.food
    return pattern


def compute_slot_score(
    trait_ids: set[str],
    slot: Slot,
    trait_defs: dict[str, TraitDef],
    trait_sources: dict[str, list[str]],
) -> tuple[int, bool, list[str]]:
    score = 0
    blocked = False
    reasons: list[str] = []
    for trait_id in sorted(trait_ids):
        trait = trait_defs.get(trait_id)
        if trait is None:
            continue
        for effect in trait.effects:
            if not slot_matches(slot, effect.match):
                continue
            sources = trait_sources.get(trait_id) or ["unknown"]
            source_text = f" from {', '.join(sources)}"
            match_pattern = _format_match_pattern(effect.match)
            if effect.block is True:
                blocked = True
                reasons.append(f"{trait_id}{source_text} BLOCK on match {match_pattern}")
            elif effect.level is not None:
                delta = LEVEL_SCORES.get(effect.level, 0)
                score += delta
                reasons.append(
                    f"{trait_id}{source_text} match {match_pattern} -> "
                    f"{effect.level} ({delta:+d})"
                )
    return score, blocked, reasons


def _declares_against(
    traits_a: set[str], traits_b: set[str], trait_defs: dict[str, TraitDef]
) -> bool:
    for trait_id in traits_a:
        trait = trait_defs.get(trait_id)
        if trait is None:
            continue
        for sep in trait.separate_from:
            if sep in traits_b:
                return True
    return False


def must_separate(
    t1: set[str], t2: set[str], trait_defs: dict[str, TraitDef]
) -> bool:
    """Symmetric: t1 and t2 share a slot conflict if either declares separate_from
    referencing a trait in the other."""
    return _declares_against(t1, t2, trait_defs) or _declares_against(t2, t1, trait_defs)
