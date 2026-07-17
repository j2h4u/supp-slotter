"""Runtime contract tests for generated scheduling constraints."""

from __future__ import annotations

from typing import cast

import planner.ontology.policies as policies
import pytest
from planner.contracts import CardLoadError, Substance
from planner.engine._plan_blocking import blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.ontology.policies import _constraint_selector, load_scheduling_constraints


def test_generated_constraints_preserve_governance_metadata() -> None:
    constraints = load_scheduling_constraints(include_retired=True)
    assert len(constraints) == 8
    assert len(load_scheduling_constraints()) == 4
    expected = {
        "sc_zinc_copper_separate_slots": ("approved", "advisory"),
        "sc_calcium_iron_separate_slots": ("approved", "advisory"),
        "sc_calcium_zinc_separate_slots": ("review_pending", "review"),
        "sc_lysine_arginine_separate_slots": ("retired", "review"),
        "sc_glycine_beta_alanine_separate_slots": ("retired", "review"),
        "sc_glycine_taurine_separate_slots": ("retired", "review"),
        "sc_mineral_fat_soluble_separate_slots": ("retired", "review"),
        "sc_tocopherol_tocotrienol_separate_slots": ("review_pending", "review"),
    }
    assert {item.id: (item.status, item.enforcement) for item in constraints} == expected
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


@pytest.mark.parametrize(
    "status,enforcement", [("proposed", "advisory"), ("review_pending", "block"), ("retired", "advisory")]
)
def test_loader_rejects_invalid_governance_matrix(
    monkeypatch: pytest.MonkeyPatch, status: str, enforcement: str
) -> None:
    original = policies.load_runtime_vocabulary
    vocabulary = cast(dict[str, object], original(policies.ROOT / "ontology"))
    constraints = dict(cast(dict[str, object], vocabulary["scheduling_constraints"]))
    record = dict(cast(dict[str, object], constraints["sc_zinc_copper_separate_slots"]))
    record["status"], record["enforcement"] = status, enforcement
    constraints["sc_zinc_copper_separate_slots"] = record

    def fake_loader(_path: object) -> dict[str, object]:
        return {**vocabulary, "scheduling_constraints": constraints}

    monkeypatch.setattr(
        policies,
        "load_runtime_vocabulary",
        fake_loader,
    )
    with pytest.raises(CardLoadError, match="status/enforcement"):
        load_scheduling_constraints(include_retired=True)


def test_loader_rejects_empty_approved_evidence_and_bad_url(monkeypatch: pytest.MonkeyPatch) -> None:
    original = policies.load_runtime_vocabulary
    vocabulary = cast(dict[str, object], original(policies.ROOT / "ontology"))
    constraints = dict(cast(dict[str, object], vocabulary["scheduling_constraints"]))
    record = dict(cast(dict[str, object], constraints["sc_zinc_copper_separate_slots"]))
    record["evidence"] = ["http://example.test/nope"]
    constraints["sc_zinc_copper_separate_slots"] = record

    def fake_loader(_path: object) -> dict[str, object]:
        return {**vocabulary, "scheduling_constraints": constraints}

    monkeypatch.setattr(
        policies,
        "load_runtime_vocabulary",
        fake_loader,
    )
    with pytest.raises(CardLoadError, match=r"evidence\[0\]"):
        load_scheduling_constraints(include_retired=True)


def test_retired_mineral_rule_is_excluded_from_runtime_blocking() -> None:
    constraints = load_scheduling_constraints()
    mineral = Substance(id="sub_m", name="Magnesium", kind=("mineral",))
    vitamin = Substance(id="sub_v", name="Vitamin D", quality=("fat_soluble",))
    blocking = BlockingContext(
        {"prd_m": ["sub_m"], "prd_v": ["sub_v"]},
        {"sub_m": mineral, "sub_v": vitamin},
        constraints,
    )
    slot_items = {"breakfast": ["prd_m"]}
    assert not slot_is_blocked("prd_v", "breakfast", slot_items, blocking)
    assert blocking_constraint_diagnostics("prd_v", "breakfast", slot_items, blocking) == ()


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
