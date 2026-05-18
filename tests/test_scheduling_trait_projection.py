"""Trait projection rules for scheduling."""

from __future__ import annotations

from planner.contracts import Product, ProductComponent, Substance, TraitDef
from planner.engine._scheduling import effective_stack_item_traits


def test_knowledge_and_context_excluded_from_scheduling_traits() -> None:
    substance = Substance(
        id="sub_zz0000zzzz",
        name="Test Substance",
        context=("sleep_recovery",),
        is_=("nootropic",),
        intake=("food_preferred",),
        timing=("sleep_support",),
    )
    substances = {"sub_zz0000zzzz": substance}
    product = Product(
        id="prd_test",
        name="Test Product",
        components=(ProductComponent(substance="sub_zz0000zzzz"),),
    )
    trait_defs = {
        "context:sleep_recovery": TraitDef(
            id="context:sleep_recovery",
            namespace="context",
            short_name="sleep_recovery",
            label="Sleep Recovery",
            description="",
            applies_when="",
        ),
        "is:nootropic": TraitDef(
            id="is:nootropic",
            namespace="is",
            short_name="nootropic",
            label="Nootropic",
            description="",
            applies_when="",
        ),
        "intake:food_preferred": TraitDef(
            id="intake:food_preferred",
            namespace="intake",
            short_name="food_preferred",
            label="Food preferred",
            description="",
            applies_when="",
        ),
        "timing:sleep_support": TraitDef(
            id="timing:sleep_support",
            namespace="timing",
            short_name="sleep_support",
            label="Sleep support",
            description="",
            applies_when="",
        ),
    }

    effective, _primary, _secondary_only, _trait_sources = effective_stack_item_traits(
        product, substances, trait_defs
    )

    assert "context:sleep_recovery" not in effective
    assert "is:nootropic" not in effective
    assert "intake:food_preferred" in effective
    assert "timing:sleep_support" in effective
