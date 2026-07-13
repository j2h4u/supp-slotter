"""Slot-assignment helpers used by `cmd_plan` (private to the engine package)."""

from __future__ import annotations

from planner.cards.substance import format_substance_name
from planner.contracts import Product, SchedulingPolicy, Slot, Substance, TraitEffect, TraitEffectMatch
from planner.domain_constants import LEVEL_SCORES


def effective_stack_item_traits(
    product: Product,
    substances: dict[str, Substance],
    policies: dict[str, SchedulingPolicy],
) -> tuple[set[str], set[str], set[str], dict[str, list[str]]]:
    """Aggregate schedule traits and sources for one physical stack item."""
    effective: set[str] = set()
    primary_traits: set[str] = set()
    trait_sources: dict[str, list[str]] = {}

    has_explicit_primary = any(c.primary is True for c in product.components)

    for component in product.components:
        component_id = component.substance
        substance = substances.get(component_id)
        if substance is None:
            continue
        is_primary = (not has_explicit_primary) or (component.primary is True)
        scheduling_traits = (
            {f"intake:{s}" for s in substance.intake}
            | {f"timing:{s}" for s in substance.timing}
            | {f"activity:{s}" for s in substance.activity}
        )
        for trait_id in scheduling_traits:
            effective.add(trait_id)
            sources = trait_sources.setdefault(trait_id, [])
            if component_id not in sources:
                sources.append(component_id)
            if is_primary:
                primary_traits.add(trait_id)

    secondary_only_traits = effective - primary_traits

    return effective, primary_traits, secondary_only_traits, trait_sources


def slot_matches(slot: Slot, match: TraitEffectMatch) -> bool:
    if match.near is not None and slot.near != match.near:
        return False
    return not (match.food is not None and slot.food != match.food)


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
    policies: dict[str, SchedulingPolicy],
) -> list[str]:
    reasons: list[str] = []
    for trait_id in sorted(trait_ids):
        trait = policies.get(trait_id)
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


def _format_match_pattern(match: TraitEffectMatch) -> dict[str, object]:
    pattern: dict[str, object] = {}
    if match.near is not None:
        pattern["near"] = match.near
    if match.food is not None:
        pattern["food"] = match.food
    return pattern


def compute_slot_score(
    trait_ids: set[str],
    slot: Slot,
    policies: dict[str, SchedulingPolicy],
    trait_sources: dict[str, list[str]],
) -> tuple[int, bool, list[str]]:
    score = 0
    blocked = False
    reasons: list[str] = []
    for trait_id in sorted(trait_ids):
        trait = policies.get(trait_id)
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
                reasons.append(f"{trait_id}{source_text} match {match_pattern} -> {effect.level} ({delta:+d})")
    return score, blocked, reasons
