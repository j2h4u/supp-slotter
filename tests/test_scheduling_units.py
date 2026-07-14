"""Unit tests for scheduling internals.

No live data directory access — no DATA_DIR reads, no disk YAML.
"""

from __future__ import annotations

from planner.contracts import (
    Product,
    ProductComponent,
    RelationSelector,
    SchedulingConstraint,
    SchedulingPolicy,
    Substance,
    TraitEffect,
    TraitEffectMatch,
)
from planner.domain_constants import LEVEL_SCORES
from planner.engine._plan_blocking import blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.engine._scheduling import compute_slot_score, effective_stack_item_traits

from tests.scheduling_fixtures import (
    NO_TRAIT_SOURCES,
    SubstanceTraitOverrides,
    make_slot,
    make_substance,
    make_trait_def,
)

# ---------------------------------------------------------------------------
# SI-04: compute_slot_score
# ---------------------------------------------------------------------------


def test_compute_slot_score_prefer_strong_match() -> None:
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="breakfast", food=True)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:with_food", effects=(effect,))
    policies = {"intake:with_food": trait}

    score, blocked, _ = compute_slot_score({"intake:with_food"}, slot, policies, NO_TRAIT_SOURCES)

    assert score == LEVEL_SCORES["prefer_strong"]
    assert score > 0
    assert blocked is False


def test_compute_slot_score_avoid_match() -> None:
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="breakfast")
    effect = TraitEffect(match=match, level="avoid")
    trait = make_trait_def("intake:empty_stomach", effects=(effect,))
    policies = {"intake:empty_stomach": trait}

    score, blocked, _ = compute_slot_score({"intake:empty_stomach"}, slot, policies, NO_TRAIT_SOURCES)

    assert score == LEVEL_SCORES["avoid"]
    assert score < 0
    assert blocked is False


def test_compute_slot_score_block_on_matching_slot() -> None:
    slot = make_slot(near="sleep", food=False)
    match = TraitEffectMatch(near="sleep")
    effect = TraitEffect(match=match, block=True)
    trait = make_trait_def("effect:stimulant", effects=(effect,))
    policies = {"effect:stimulant": trait}

    score, blocked, _ = compute_slot_score({"effect:stimulant"}, slot, policies, NO_TRAIT_SOURCES)

    assert blocked is True
    assert score == 0


def test_compute_slot_score_empty_traits() -> None:
    slot = make_slot()
    score, blocked, _ = compute_slot_score(set(), slot, {}, NO_TRAIT_SOURCES)

    assert score == 0
    assert blocked is False


def test_compute_slot_score_no_matching_effects() -> None:
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near="sleep")
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:night_only", effects=(effect,))
    policies = {"intake:night_only": trait}

    score, blocked, _ = compute_slot_score({"intake:night_only"}, slot, policies, NO_TRAIT_SOURCES)

    assert score == 0
    assert blocked is False


def test_compute_slot_score_food_axis_match() -> None:
    # food=False match fires on a food=False slot regardless of near value (wildcard).
    slot = make_slot(near="breakfast", food=False)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:empty_stomach_food_axis", effects=(effect,))
    policies = {"intake:empty_stomach_food_axis": trait}

    score, blocked, _ = compute_slot_score({"intake:empty_stomach_food_axis"}, slot, policies, NO_TRAIT_SOURCES)

    assert score == LEVEL_SCORES["prefer_strong"]
    assert blocked is False


def test_compute_slot_score_food_axis_mismatch() -> None:
    # food=False effect does not fire on a food=True slot — discriminant blocks accumulation.
    slot = make_slot(near="breakfast", food=True)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, level="prefer_strong")
    trait = make_trait_def("intake:empty_stomach_food_axis", effects=(effect,))
    policies = {"intake:empty_stomach_food_axis": trait}

    score, blocked, _ = compute_slot_score({"intake:empty_stomach_food_axis"}, slot, policies, NO_TRAIT_SOURCES)

    assert score == 0
    assert blocked is False


def test_compute_slot_score_food_axis_block() -> None:
    # block path fires when food axis matches — blocked is True.
    slot = make_slot(near="breakfast", food=False)
    match = TraitEffectMatch(near=None, food=False)
    effect = TraitEffect(match=match, block=True)
    trait = make_trait_def("effect:food_blocker", effects=(effect,))
    policies = {"effect:food_blocker": trait}

    _, blocked, _ = compute_slot_score({"effect:food_blocker"}, slot, policies, NO_TRAIT_SOURCES)

    assert blocked is True


def test_scheduling_traits_exclude_risk_and_knowledge_effect() -> None:
    """effective_stack_item_traits must not include risk: or knowledge.effect: slugs.

    Only schedule.* fields (intake, timing, activity) contribute to the scheduling
    traits set. knowledge.* fields (risk, effect, is_, context, pathway) are
    Reviewer-only and must not appear in the effective set that drives slot assignment.
    """
    sub = make_substance(
        "sub_zz9999zzzz",
        "Test Mineral",
        traits=SubstanceTraitOverrides(
            intake=("food_preferred",),
            timing=("sleep_support",),
            risk=("manual_review",),
            effect=("vasodilator",),
            kind=("mineral",),
        ),
    )
    substances = {"sub_zz9999zzzz": sub}

    product = Product(
        id="prd_test",
        name="Test Product",
        components=(ProductComponent(substance="sub_zz9999zzzz"),),
    )

    policies: dict[str, SchedulingPolicy] = {}  # empty — no scoring rules needed for this assertion

    effective, _primary, _secondary_only, _trait_sources = effective_stack_item_traits(product, substances, policies)

    # schedule.* fields ARE included
    assert "intake:food_preferred" in effective, "intake: slug must be in scheduling traits"
    assert "timing:sleep_support" in effective, "timing: slug must be in scheduling traits"
    # knowledge.* fields are NOT included
    assert "risk:manual_review" not in effective, (
        "risk: slugs must be excluded from scheduling traits (knowledge: field)"
    )
    assert "effect:vasodilator" not in effective, (
        "effect: slugs must be excluded from scheduling traits (knowledge: field)"
    )
    assert "is:mineral" not in effective, "is: slugs must be excluded from scheduling traits (knowledge: field)"


def test_make_substance_factory_accepts_timing() -> None:
    """make_substance factory passes timing kwarg to Substance."""
    sub = make_substance("sub_zz8888zzzz", traits=SubstanceTraitOverrides(timing=("sleep_support",)))
    assert sub.timing == ("sleep_support",), f"Expected timing=('sleep_support',), got {sub.timing!r}"


# ---------------------------------------------------------------------------
# First-class scheduling constraints (slot_is_blocked)
# ---------------------------------------------------------------------------


def _mineral_fat_soluble_constraint() -> SchedulingConstraint:
    return SchedulingConstraint(
        id="sc_test_mineral_fat_soluble",
        source_selector=RelationSelector(category="kind", term="mineral"),
        target_selector=RelationSelector(category="quality", term="fat_soluble"),
        effect="separate_slots",
        enforcement="block",
        status="approved",
        evidence=("https://example.test/evidence",),
    )


def _product_with_primary_component(product_id: str, name: str, substance_id: str) -> Product:
    return Product(
        id=product_id,
        name=name,
        components=(ProductComponent(substance=substance_id, primary=True),),
    )


def _class_constraint_blocked(
    new_product: Product,
    existing_product: Product,
    substances: dict[str, Substance],
    scheduling_constraints: tuple[SchedulingConstraint, ...],
) -> bool:
    slot_name = "breakfast"
    new_substance_id = new_product.components[0].substance
    existing_substance_id = existing_product.components[0].substance
    active_components: dict[str, list[str]] = {
        existing_product.id: [existing_substance_id],
        new_product.id: [new_substance_id],
    }
    blocking = BlockingContext(active_components, substances, scheduling_constraints)
    return slot_is_blocked(
        new_product.id,
        slot_name,
        {slot_name: [existing_product.id]},
        blocking,
    )


def test_class_level_constraint_blocks_slot() -> None:
    """A mineral and a fat_soluble substance must not share a slot."""
    mineral_sub = make_substance("sub_mineral0001", "Zinc", traits=SubstanceTraitOverrides(kind=("mineral",)))
    fat_sol_sub = make_substance("sub_fatsoluble1", "Vitamin D")
    fat_sol_sub = Substance(
        id=fat_sol_sub.id,
        name=fat_sol_sub.name,
        quality=("fat_soluble",),
    )
    mineral_prd = Product(
        id="prd_mineral0001",
        name="Zinc Product",
        components=(ProductComponent(substance="sub_mineral0001", primary=True),),
    )
    fat_sol_prd = Product(
        id="prd_fatsoluble1",
        name="Vitamin D Product",
        components=(ProductComponent(substance="sub_fatsoluble1", primary=True),),
    )
    substances = {
        "sub_mineral0001": mineral_sub,
        "sub_fatsoluble1": fat_sol_sub,
    }
    slot_name = "breakfast"
    # mineral already placed in slot
    slot_items: dict[str, list[str]] = {slot_name: [mineral_prd.id]}
    active_components: dict[str, list[str]] = {
        mineral_prd.id: ["sub_mineral0001"],
        fat_sol_prd.id: ["sub_fatsoluble1"],
    }
    blocking = BlockingContext(active_components, substances, (_mineral_fat_soluble_constraint(),))

    result = slot_is_blocked(
        fat_sol_prd.id,
        slot_name,
        slot_items,
        blocking,
    )

    assert result is True, "mineral ↔ fat_soluble constraint must block co-placement"


def test_unknown_candidate_and_existing_ids_are_unblocked_without_diagnostics() -> None:
    blocking = BlockingContext({}, {}, (_mineral_fat_soluble_constraint(),))
    slot_items = {"breakfast": ["unknown_existing"]}

    assert slot_is_blocked("unknown_candidate", "breakfast", slot_items, blocking) is False
    assert blocking_constraint_diagnostics("unknown_candidate", "breakfast", slot_items, blocking) == ()


def test_class_level_constraint_does_not_block_unrelated_classes() -> None:
    """An amino substance is not blocked by the mineral ↔ fat_soluble rule."""
    mineral_sub = make_substance("sub_mineral0002", "Magnesium", traits=SubstanceTraitOverrides(kind=("mineral",)))
    amino_sub = make_substance("sub_amino00001", "Glycine", traits=SubstanceTraitOverrides(kind=("amino",)))
    mineral_prd = Product(
        id="prd_mineral0002",
        name="Magnesium Product",
        components=(ProductComponent(substance="sub_mineral0002", primary=True),),
    )
    amino_prd = Product(
        id="prd_amino00001",
        name="Glycine Product",
        components=(ProductComponent(substance="sub_amino00001", primary=True),),
    )
    substances = {
        "sub_mineral0002": mineral_sub,
        "sub_amino00001": amino_sub,
    }
    slot_name = "breakfast"
    slot_items: dict[str, list[str]] = {slot_name: [mineral_prd.id]}
    active_components: dict[str, list[str]] = {
        mineral_prd.id: ["sub_mineral0002"],
        amino_prd.id: ["sub_amino00001"],
    }
    blocking = BlockingContext(active_components, substances, (_mineral_fat_soluble_constraint(),))

    result = slot_is_blocked(
        amino_prd.id,
        slot_name,
        slot_items,
        blocking,
    )

    assert result is False, "amino class is not covered by mineral ↔ fat_soluble rule"


def test_class_level_constraint_is_symmetric() -> None:
    """Blocking is symmetric: swapping item and existing still returns True."""
    mineral_sub = make_substance("sub_mineral0003", "Copper", traits=SubstanceTraitOverrides(kind=("mineral",)))
    fat_sol_sub = Substance(id="sub_fatsoluble2", name="Vitamin K", quality=("fat_soluble",))
    mineral_prd = _product_with_primary_component("prd_mineral0003", "Copper Product", "sub_mineral0003")
    fat_sol_prd = _product_with_primary_component("prd_fatsoluble2", "Vitamin K Product", "sub_fatsoluble2")
    substances = {
        "sub_mineral0003": mineral_sub,
        "sub_fatsoluble2": fat_sol_sub,
    }
    constraints = (_mineral_fat_soluble_constraint(),)

    result_a = _class_constraint_blocked(fat_sol_prd, mineral_prd, substances, constraints)
    result_b = _class_constraint_blocked(mineral_prd, fat_sol_prd, substances, constraints)

    assert result_a is True, "fat_soluble blocked by mineral (direction 1)"
    assert result_b is True, "mineral blocked by fat_soluble (direction 2) — symmetric"
