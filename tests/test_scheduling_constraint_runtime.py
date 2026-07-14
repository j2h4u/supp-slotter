"""Runtime contract tests for generated scheduling constraints."""

from __future__ import annotations

import pytest
from planner.contracts import CardLoadError, Substance
from planner.engine._plan_blocking import blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.ontology.policies import _constraint_selector, load_scheduling_constraints


def test_generated_constraints_preserve_governance_metadata() -> None:
    constraints = load_scheduling_constraints()
    assert len(constraints) == 8
    assert all(constraint.rationale and constraint.status and constraint.owner for constraint in constraints)
    assert all(constraint.assertion_type == "clinical_scheduling_constraint" for constraint in constraints)
    mineral = next(item for item in constraints if item.id == "sc_mineral_fat_soluble_separate_slots")
    assert mineral.semantic_note
    assert mineral.legacy_relation_id == "rel_competes_007"
    assert mineral.scope == (("planner", "separate_products_same_slot"),)


@pytest.mark.parametrize(
    "selector",
    [
        {"entity": {"id": "sub_x", "name": "X"}},
        {"entity": {}},
        {"category": "kind"},
        {"category": "kind", "term": ""},
        {"entity": {"id": "sub_x"}, "category": "kind", "term": "mineral"},
    ],
)
def test_malformed_selector_fails_fast(selector: object) -> None:
    with pytest.raises(CardLoadError):
        _constraint_selector(selector)


def test_diagnostics_match_boolean_and_identify_mineral_rule() -> None:
    constraints = load_scheduling_constraints()
    mineral = Substance(id="sub_m", name="Magnesium", kind=("mineral",))
    vitamin = Substance(id="sub_v", name="Vitamin D", quality=("fat_soluble",))
    blocking = BlockingContext(
        {"prd_m": ["sub_m"], "prd_v": ["sub_v"]},
        {"sub_m": mineral, "sub_v": vitamin},
        constraints,
    )
    slot_items = {"breakfast": ["prd_m"]}
    assert slot_is_blocked("prd_v", "breakfast", slot_items, blocking)
    diagnostics = blocking_constraint_diagnostics("prd_v", "breakfast", slot_items, blocking)
    assert [item.id for item in diagnostics] == ["sc_mineral_fat_soluble_separate_slots"]
    assert diagnostics[0].action is None
    assert diagnostics[0].metadata["legacy_relation_id"] == "rel_competes_007"


def test_unknown_or_empty_slot_is_not_blocked_and_has_no_diagnostics() -> None:
    blocking = BlockingContext(
        {"prd_m": ["sub_m"]},
        {"sub_m": Substance(id="sub_m", name="Magnesium", kind=("mineral",))},
        load_scheduling_constraints(),
    )
    slot_item_cases: tuple[dict[str, list[str]], ...] = ({}, {"breakfast": []})
    for slot_items in slot_item_cases:
        assert slot_is_blocked("prd_m", "breakfast", slot_items, blocking) is False
        assert blocking_constraint_diagnostics("prd_m", "breakfast", slot_items, blocking) == ()
