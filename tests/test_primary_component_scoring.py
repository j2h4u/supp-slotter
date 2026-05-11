"""Tests for primary-component scoring split (260510-lwy).

All fixtures are built inline using dataclass constructors.
No live data directory access — no DATA_DIR reads, no disk YAML.
"""

from __future__ import annotations

from planner.contracts import (
    Product,
    ProductComponent,
    Slot,
    Substance,
    TraitDef,
    TraitEffect,
    TraitEffectMatch,
)
from planner.engine._scheduling import (
    compute_slot_score,
    effective_stack_item_traits,
)
from planner.io import LEVEL_SCORES, SECONDARY_TRAIT_WEIGHT


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_scheduling_units.py style)
# ---------------------------------------------------------------------------

def make_slot(
    near: str = "breakfast",
    food: bool = True,
    slot_id: str = "test_slot",
    stack: str = "daily",
) -> Slot:
    return Slot(
        slot_id=slot_id,
        label="Test Slot",
        order=1,
        near=near,  # type: ignore[arg-type]
        food=food,
        pillbox="daily",
        pillbox_label="Daily",
        stack=stack,
    )


def make_trait_def(
    trait_id: str,
    *,
    effects: tuple[TraitEffect, ...] = (),
    separate_from: tuple[str, ...] = (),
) -> TraitDef:
    return TraitDef(
        id=trait_id,
        namespace="intake",
        short_name=trait_id,
        label=trait_id,
        description="",
        applies_when="always",
        effects=effects,
        separate_from=separate_from,
    )


def make_substance(
    sub_id: str,
    *,
    intake: tuple[str, ...] = (),
    effect: tuple[str, ...] = (),
    is_: tuple[str, ...] = (),
    risk: tuple[str, ...] = (),
    activity: tuple[str, ...] = (),
    dashboard: tuple[str, ...] = (),
) -> Substance:
    return Substance(
        id=sub_id, name=sub_id,
        intake=intake, effect=effect, is_=is_,
        risk=risk, activity=activity, dashboard=dashboard,
    )


def make_product_with_components(prd_id: str, components: tuple[ProductComponent, ...]) -> Product:
    return Product(id=prd_id, name=prd_id, components=components)


_NO_SOURCES: dict[str, list[str]] = {}


# ---------------------------------------------------------------------------
# PC-01: effective_stack_item_traits 5-tuple split
# ---------------------------------------------------------------------------

def test_effective_stack_item_traits_primary_secondary_split() -> None:
    """Primary traits in primary_traits; secondary-only traits in secondary_only_traits."""
    primary_component = ProductComponent(substance="sub_primary", primary=True)
    secondary_component = ProductComponent(substance="sub_secondary", primary=False)
    product = make_product_with_components(
        "prd_test",
        (primary_component, secondary_component),
    )

    substances = {
        "sub_primary": make_substance("sub_primary", intake=("empty_preferred",)),
        "sub_secondary": make_substance("sub_secondary", intake=("fat_meal_required",)),
    }
    trait_defs: dict[str, TraitDef] = {}

    effective, primary_traits, secondary_only_traits, trait_sources, internal_conflicts = (
        effective_stack_item_traits(product, substances, trait_defs)
    )

    assert effective == {"intake:empty_preferred", "intake:fat_meal_required"}
    assert primary_traits == {"intake:empty_preferred"}
    assert secondary_only_traits == {"intake:fat_meal_required"}
    assert "intake:empty_preferred" in trait_sources
    assert "intake:fat_meal_required" in trait_sources
    assert internal_conflicts == []


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
        "sub_shared": make_substance("sub_shared", intake=("with_food",)),
        "sub_secondary": make_substance("sub_secondary", intake=("with_food",)),
    }
    trait_defs: dict[str, TraitDef] = {}

    _effective, primary_traits, secondary_only_traits, _sources, _conflicts = (
        effective_stack_item_traits(product, substances, trait_defs)
    )

    assert shared_trait in primary_traits
    assert shared_trait not in secondary_only_traits


def test_effective_stack_item_traits_all_secondary_fallback() -> None:
    """No explicit primary=True: fallback makes all components primary, secondary_only empty."""
    comp_a = ProductComponent(substance="sub_a", primary=False)
    comp_b = ProductComponent(substance="sub_b", primary=False)
    product = make_product_with_components("prd_all_sec", (comp_a, comp_b))
    substances = {
        "sub_a": make_substance("sub_a", intake=("empty_preferred",)),
        "sub_b": make_substance("sub_b", intake=("fat_meal_required",)),
    }
    trait_defs: dict[str, TraitDef] = {}

    effective, primary_traits, secondary_only_traits, _sources, _conflicts = (
        effective_stack_item_traits(product, substances, trait_defs)
    )

    # No sibling has primary=True, so fallback: all treated as primary.
    assert primary_traits == effective
    assert secondary_only_traits == set()


# ---------------------------------------------------------------------------
# PC-02: SECONDARY_TRAIT_WEIGHT value and formula
# ---------------------------------------------------------------------------

def test_secondary_trait_weight_value() -> None:
    """SECONDARY_TRAIT_WEIGHT must evaluate to exactly 0.25 given current LEVEL_SCORES."""
    assert SECONDARY_TRAIT_WEIGHT == 0.25


def test_secondary_trait_weight_formula() -> None:
    """Formula: (prefer - avoid) / (4 * prefer_strong)."""
    expected = (
        (LEVEL_SCORES["prefer"] - LEVEL_SCORES["avoid"])
        / (4 * LEVEL_SCORES["prefer_strong"])
    )
    assert SECONDARY_TRAIT_WEIGHT == expected


# ---------------------------------------------------------------------------
# PC-03: Integration — primary driver wins over secondary preference
# ---------------------------------------------------------------------------

def _build_nattokinase_like_scenario() -> tuple[
    Product,
    dict[str, Substance],
    dict[str, TraitDef],
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
    trait_defs = {
        "intake:empty_preferred": empty_preferred_trait,
        "intake:fat_meal_required": fat_meal_trait,
    }

    # Substances
    primary_sub = make_substance("sub_natto", intake=("empty_preferred",))
    secondary_sub = make_substance("sub_epa", intake=("fat_meal_required",))
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

    return product, substances, trait_defs, empty_slot, fat_slot


def test_primary_wins_over_secondary_empty_slot_preferred() -> None:
    """Primary intake:empty_preferred beats secondary intake:fat_meal_required."""
    product, substances, trait_defs, empty_slot, fat_slot = (
        _build_nattokinase_like_scenario()
    )

    effective, primary_traits, secondary_only_traits, trait_sources, _ = (
        effective_stack_item_traits(product, substances, trait_defs)
    )

    # Compute combined score for each slot using the same logic as cmd_plan.
    score_traits = primary_traits if primary_traits else effective

    empty_primary_score, _blocked, _ = compute_slot_score(
        score_traits, empty_slot, trait_defs, trait_sources
    )
    fat_primary_score, _blocked2, _ = compute_slot_score(
        score_traits, fat_slot, trait_defs, trait_sources
    )

    empty_sec_score, _, _ = compute_slot_score(
        secondary_only_traits, empty_slot, trait_defs, trait_sources
    )
    fat_sec_score, _, _ = compute_slot_score(
        secondary_only_traits, fat_slot, trait_defs, trait_sources
    )

    empty_total = empty_primary_score + int(round(empty_sec_score * SECONDARY_TRAIT_WEIGHT))
    fat_total = fat_primary_score + int(round(fat_sec_score * SECONDARY_TRAIT_WEIGHT))

    # The product should score higher in the empty slot than the fat-meal slot.
    assert empty_total > fat_total, (
        f"Expected empty_slot score ({empty_total}) > fat_slot score ({fat_total})"
    )


def test_flat_union_without_primary_split_would_prefer_fat_slot() -> None:
    """Regression guard: without the primary split, fat-meal slot wins (old behaviour).

    This test documents WHY the split was needed. If the flat union is used,
    both prefer_strong traits cancel: empty_slot gets prefer_strong from natto
    but nothing from EPA; fat_slot gets prefer_strong from EPA but nothing from natto.
    With symmetrical flat weights they tie (or EPA's fat_meal_required dominates in
    some configurations). The split ensures natto drives at full weight.
    """
    product, substances, trait_defs, empty_slot, fat_slot = (
        _build_nattokinase_like_scenario()
    )

    effective, primary_traits, secondary_only_traits, trait_sources, _ = (
        effective_stack_item_traits(product, substances, trait_defs)
    )

    # Flat-union scoring (old behaviour) — both slots get one prefer_strong each.
    flat_empty_score, _, _ = compute_slot_score(effective, empty_slot, trait_defs, trait_sources)
    flat_fat_score, _, _ = compute_slot_score(effective, fat_slot, trait_defs, trait_sources)

    # Under flat scoring, both scores are equal (one prefer_strong each).
    # The primary split breaks the tie in favour of empty_slot.
    assert flat_empty_score == flat_fat_score, (
        "Flat-union scores should tie — if this fails, the test scenario changed."
    )


# ---------------------------------------------------------------------------
# PC-04: All-secondary product still gets scheduled (fallback path)
# ---------------------------------------------------------------------------

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
        "sub_epa": make_substance("sub_epa", intake=("fat_meal_required",)),
    }
    trait_defs = {"intake:fat_meal_required": fat_meal_trait}

    effective, primary_traits, secondary_only_traits, trait_sources, _ = (
        effective_stack_item_traits(product, substances, trait_defs)
    )

    # Fallback: score_traits == effective (not primary_traits which is empty)
    score_traits = primary_traits if primary_traits else effective

    fat_slot = make_slot(near="breakfast", food=True, slot_id="morning_food", stack="daily")
    score, blocked, _ = compute_slot_score(score_traits, fat_slot, trait_defs, trait_sources)

    assert not blocked
    assert score > 0, "All-secondary product must still score in a matching slot (fallback path)"
