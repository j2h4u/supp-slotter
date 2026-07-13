"""Tests for primary-component scoring split.

All fixtures are built inline using dataclass constructors.
No live data directory access — no DATA_DIR reads, no disk YAML.
"""

from __future__ import annotations

from dataclasses import dataclass

from planner.contracts import (
    Product,
    ProductComponent,
    SchedulingPolicy,
    Slot,
    SlotNear,
    Substance,
    TraitEffect,
    TraitEffectMatch,
)
from planner.domain_constants import LEVEL_SCORES, SECONDARY_TRAIT_WEIGHT
from planner.engine._scheduling import (
    compute_slot_score,
    effective_stack_item_traits,
)

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_scheduling_units.py style)
# ---------------------------------------------------------------------------


def make_slot(
    near: SlotNear = "breakfast",
    food: bool = True,
    slot_id: str = "test_slot",
    stack: str = "daily",
) -> Slot:
    return Slot(
        slot_id=slot_id,
        label="Test Slot",
        order=1,
        near=near,
        food=food,
        pillbox="daily",
        pillbox_label="Daily",
        stack=stack,
    )


def make_trait_def(
    trait_id: str,
    *,
    effects: tuple[TraitEffect, ...] = (),
) -> SchedulingPolicy:
    return SchedulingPolicy(
        id=trait_id,
        namespace="intake",
        short_name=trait_id,
        label=trait_id,
        description="",
        applies_when="always",
        effects=effects,
    )


@dataclass(frozen=True, slots=True)
class SubstanceTraitOverrides:
    intake: tuple[str, ...] = ()
    timing: tuple[str, ...] = ()
    effect: tuple[str, ...] = ()
    kind: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    activity: tuple[str, ...] = ()
    context: tuple[str, ...] = ()


_NO_SUBSTANCE_TRAIT_OVERRIDES = SubstanceTraitOverrides()


def make_substance(
    sub_id: str,
    *,
    traits: SubstanceTraitOverrides = _NO_SUBSTANCE_TRAIT_OVERRIDES,
) -> Substance:
    return Substance(
        id=sub_id,
        name=sub_id,
        intake=traits.intake,
        timing=traits.timing,
        effect=traits.effect,
        kind=traits.kind,
        risk=traits.risk,
        activity=traits.activity,
        context=traits.context,
    )


def make_product_with_components(prd_id: str, components: tuple[ProductComponent, ...]) -> Product:
    return Product(id=prd_id, name=prd_id, components=components)


_NO_SOURCES: dict[str, list[str]] = {}


def test_effective_stack_item_traits_primary_secondary_split() -> None:
    """Primary traits in primary_traits; secondary-only traits in secondary_only_traits."""
    primary_component = ProductComponent(substance="sub_primary", primary=True)
    secondary_component = ProductComponent(substance="sub_secondary", primary=False)
    product = make_product_with_components(
        "prd_test",
        (primary_component, secondary_component),
    )

    substances = {
        "sub_primary": make_substance("sub_primary", traits=SubstanceTraitOverrides(intake=("empty_preferred",))),
        "sub_secondary": make_substance("sub_secondary", traits=SubstanceTraitOverrides(intake=("fat_meal_required",))),
    }
    policies: dict[str, SchedulingPolicy] = {}

    effective, primary_traits, secondary_only_traits, trait_sources = effective_stack_item_traits(
        product, substances, policies
    )

    assert effective == {"intake:empty_preferred", "intake:fat_meal_required"}
    assert primary_traits == {"intake:empty_preferred"}
    assert secondary_only_traits == {"intake:fat_meal_required"}
    assert "intake:empty_preferred" in trait_sources
    assert "intake:fat_meal_required" in trait_sources


def test_effective_stack_item_traits_shared_trait_is_primary() -> None:
    """A trait carried by both a primary and a secondary component is primary, not secondary."""
    shared_component = ProductComponent(substance="sub_shared", primary=True)
    secondary_component = ProductComponent(substance="sub_secondary", primary=False)
    # Give both components the same trait.
    product = make_product_with_components(
        "prd_shared",
        (shared_component, secondary_component),
    )
    shared_trait = "intake:with_food"
    substances = {
        "sub_shared": make_substance("sub_shared", traits=SubstanceTraitOverrides(intake=("with_food",))),
        "sub_secondary": make_substance("sub_secondary", traits=SubstanceTraitOverrides(intake=("with_food",))),
    }
    policies: dict[str, SchedulingPolicy] = {}

    _effective, primary_traits, secondary_only_traits, _sources = effective_stack_item_traits(
        product, substances, policies
    )

    assert shared_trait in primary_traits
    assert shared_trait not in secondary_only_traits


def test_effective_stack_item_traits_all_secondary_fallback() -> None:
    """No explicit primary=True: fallback makes all components primary, secondary_only empty."""
    comp_a = ProductComponent(substance="sub_a", primary=False)
    comp_b = ProductComponent(substance="sub_b", primary=False)
    product = make_product_with_components("prd_all_sec", (comp_a, comp_b))
    substances = {
        "sub_a": make_substance("sub_a", traits=SubstanceTraitOverrides(intake=("empty_preferred",))),
        "sub_b": make_substance("sub_b", traits=SubstanceTraitOverrides(intake=("fat_meal_required",))),
    }
    policies: dict[str, SchedulingPolicy] = {}

    effective, primary_traits, secondary_only_traits, _sources = effective_stack_item_traits(
        product, substances, policies
    )

    # No sibling has primary=True, so fallback: all treated as primary.
    assert primary_traits == effective
    assert secondary_only_traits == set()


def test_effective_stack_item_traits_tracks_timing_activity_and_missing_components() -> None:
    product = make_product_with_components(
        "prd_mixed",
        (
            ProductComponent(substance="sub_primary", primary=True),
            ProductComponent(substance="sub_missing", primary=False),
            ProductComponent(substance="sub_secondary", primary=None),
        ),
    )
    substances = {
        "sub_primary": make_substance(
            "sub_primary",
            traits=SubstanceTraitOverrides(
                intake=("empty_preferred",),
                timing=("wake",),
                activity=("workout_before",),
            ),
        ),
        "sub_secondary": make_substance(
            "sub_secondary",
            traits=SubstanceTraitOverrides(
                intake=("with_food",),
                activity=("workout_after",),
            ),
        ),
    }

    effective, primary_traits, secondary_only_traits, trait_sources = effective_stack_item_traits(
        product, substances, {}
    )

    assert effective == {
        "intake:empty_preferred",
        "timing:wake",
        "activity:workout_before",
        "intake:with_food",
        "activity:workout_after",
    }
    assert primary_traits == {
        "intake:empty_preferred",
        "timing:wake",
        "activity:workout_before",
    }
    assert secondary_only_traits == {"intake:with_food", "activity:workout_after"}
    assert trait_sources["activity:workout_before"] == ["sub_primary"]
    assert trait_sources["activity:workout_after"] == ["sub_secondary"]


def test_secondary_trait_weight_value() -> None:
    """SECONDARY_TRAIT_WEIGHT must evaluate to exactly 0.25 given current LEVEL_SCORES."""
    assert SECONDARY_TRAIT_WEIGHT == 0.25


def test_secondary_trait_weight_formula() -> None:
    """Formula: (prefer - avoid) / (4 * prefer_strong)."""
    expected = (LEVEL_SCORES["prefer"] - LEVEL_SCORES["avoid"]) / (4 * LEVEL_SCORES["prefer_strong"])
    assert expected == SECONDARY_TRAIT_WEIGHT


def _build_nattokinase_like_scenario() -> tuple[
    Product,
    dict[str, Substance],
    dict[str, SchedulingPolicy],
    Slot,
    Slot,
]:
    """
    Minimal scenario mirroring Nattokinase 13000FU:
    - Primary substance: prefers empty_preferred slot (prefer_strong)
    - Secondary substance: prefers fat_meal slot (prefer_strong)

    Two slots available:
      - empty_slot: near=wake, food=False  → matches empty_preferred
      - fat_slot:   near=breakfast, food=True → matches fat_meal_required
    """
    # Trait defs
    empty_preferred_trait = make_trait_def(
        "intake:empty_preferred",
        effects=(
            TraitEffect(
                match=TraitEffectMatch(food=False),
                level="prefer_strong",
            ),
        ),
    )
    fat_meal_trait = make_trait_def(
        "intake:fat_meal_required",
        effects=(
            TraitEffect(
                match=TraitEffectMatch(food=True),
                level="prefer_strong",
            ),
        ),
    )
    policies = {
        "intake:empty_preferred": empty_preferred_trait,
        "intake:fat_meal_required": fat_meal_trait,
    }

    # Substances
    primary_sub = make_substance("sub_natto", traits=SubstanceTraitOverrides(intake=("empty_preferred",)))
    secondary_sub = make_substance("sub_epa", traits=SubstanceTraitOverrides(intake=("fat_meal_required",)))
    substances = {
        "sub_natto": primary_sub,
        "sub_epa": secondary_sub,
    }

    # Product
    product = make_product_with_components(
        "prd_natto_like",
        (
            ProductComponent(substance="sub_natto", primary=True),
            ProductComponent(substance="sub_epa", primary=False),
        ),
    )

    # Slots
    empty_slot = make_slot(near="wake", food=False, slot_id="morning_empty", stack="daily")
    fat_slot = make_slot(near="breakfast", food=True, slot_id="morning_food", stack="daily")

    return product, substances, policies, empty_slot, fat_slot


def _combined_slot_score(
    product: Product,
    substances: dict[str, Substance],
    policies: dict[str, SchedulingPolicy],
    slot: Slot,
) -> int:
    effective, primary_traits, secondary_only_traits, trait_sources = effective_stack_item_traits(
        product, substances, policies
    )
    score_traits = primary_traits or effective
    primary_score, _blocked, _ = compute_slot_score(score_traits, slot, policies, trait_sources)
    secondary_score, _sec_blocked, _ = compute_slot_score(secondary_only_traits, slot, policies, trait_sources)
    return primary_score + round(secondary_score * SECONDARY_TRAIT_WEIGHT)


def test_primary_wins_over_secondary_empty_slot_preferred() -> None:
    """Primary intake:empty_preferred beats secondary intake:fat_meal_required."""
    product, substances, policies, empty_slot, fat_slot = _build_nattokinase_like_scenario()

    empty_total = _combined_slot_score(product, substances, policies, empty_slot)
    fat_total = _combined_slot_score(product, substances, policies, fat_slot)

    # The product should score higher in the empty slot than the fat-meal slot.
    assert empty_total > fat_total, f"Expected empty_slot score ({empty_total}) > fat_slot score ({fat_total})"


def test_all_secondary_product_scores_nonzero_in_matching_slot() -> None:
    """A product with all primary=False components falls back to full-union scoring."""
    comp = ProductComponent(substance="sub_epa", primary=False)
    product = make_product_with_components("prd_all_sec2", (comp,))
    fat_meal_trait = make_trait_def(
        "intake:fat_meal_required",
        effects=(
            TraitEffect(
                match=TraitEffectMatch(food=True),
                level="prefer_strong",
            ),
        ),
    )
    substances = {
        "sub_epa": make_substance("sub_epa", traits=SubstanceTraitOverrides(intake=("fat_meal_required",))),
    }
    policies = {"intake:fat_meal_required": fat_meal_trait}

    effective, primary_traits, _secondary_only_traits, trait_sources = effective_stack_item_traits(
        product, substances, policies
    )

    # Fallback: score_traits == effective (not primary_traits which is empty)
    score_traits = primary_traits or effective

    fat_slot = make_slot(near="breakfast", food=True, slot_id="morning_food", stack="daily")
    score, blocked, _ = compute_slot_score(score_traits, fat_slot, policies, trait_sources)

    assert not blocked
    assert score > 0, "All-secondary product must still score in a matching slot (fallback path)"
