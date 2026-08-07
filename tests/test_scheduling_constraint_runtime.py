"""Runtime contract tests for generated scheduling constraints."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from planner.contracts import CardLoadError, Substance
from planner.engine._plan_blocking import blocking_constraint_diagnostics, slot_is_blocked
from planner.engine._plan_types import BlockingContext
from planner.ontology.artifacts import OntologyBundle
from planner.ontology.policies import _constraint_selector, load_scheduling_constraints
from planner.scheduling_constraint_execution import compile_scheduling_constraint_execution_plans

from tests.helpers import ontology_bundle


def test_generated_constraints_preserve_governance_metadata() -> None:
    bundle = ontology_bundle()
    constraints = load_scheduling_constraints(bundle, include_retired=True)
    assert len(constraints) == 8
    assert len(load_scheduling_constraints(bundle)) == 4
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
    assert mineral.status == "retired"


@pytest.mark.parametrize(
    "selector",
    [
        {"entity": {}},
    ],
)
def test_malformed_selector_fails_fast(selector: object) -> None:
    with pytest.raises(CardLoadError):
        _constraint_selector(selector)


@pytest.mark.parametrize("status,enforcement", [("review_pending", "block")])
def test_loader_rejects_invalid_governance_matrix(
    monkeypatch: pytest.MonkeyPatch, status: str, enforcement: str
) -> None:
    bundle = ontology_bundle()
    vocabulary = dict(bundle.runtime_vocabulary)
    constraints = dict(cast(dict[str, object], vocabulary["scheduling_constraints"]))
    record = dict(cast(dict[str, object], constraints["sc_zinc_copper_separate_slots"]))
    record["status"], record["enforcement"] = status, enforcement
    constraints["sc_zinc_copper_separate_slots"] = record

    del monkeypatch
    with pytest.raises(CardLoadError, match="status/enforcement"):
        load_scheduling_constraints(
            _bundle_with_vocabulary(bundle, {**vocabulary, "scheduling_constraints": constraints}), include_retired=True
        )


def test_loader_rejects_empty_approved_evidence_and_bad_url(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = ontology_bundle()
    vocabulary = dict(bundle.runtime_vocabulary)
    constraints = dict(cast(dict[str, object], vocabulary["scheduling_constraints"]))
    record = dict(cast(dict[str, object], constraints["sc_zinc_copper_separate_slots"]))
    record["evidence"] = ["http://example.test/nope"]
    constraints["sc_zinc_copper_separate_slots"] = record

    del monkeypatch
    with pytest.raises(CardLoadError, match=r"evidence\[0\]"):
        load_scheduling_constraints(
            _bundle_with_vocabulary(bundle, {**vocabulary, "scheduling_constraints": constraints}), include_retired=True
        )


def test_retired_mineral_rule_is_excluded_from_runtime_blocking() -> None:
    bundle = ontology_bundle()
    constraints = load_scheduling_constraints(bundle)
    mineral = Substance(id="sub_m", name="Magnesium", kind=("mineral",))
    vitamin = Substance(id="sub_v", name="Vitamin D", quality=("fat_soluble",))
    blocking = BlockingContext(
        {"prd_m": ["sub_m"], "prd_v": ["sub_v"]},
        {"sub_m": mineral, "sub_v": vitamin},
        compile_scheduling_constraint_execution_plans(
            constraints,
            {"sub_m": mineral, "sub_v": vitamin},
            bundle.runtime_program,
            allow_empty_selector_resolution=True,
        ),
    )
    slot_items = {"breakfast": ["prd_m"]}
    assert not slot_is_blocked("prd_v", "breakfast", slot_items, blocking)
    assert blocking_constraint_diagnostics("prd_v", "breakfast", slot_items, blocking) == ()


def test_unknown_or_empty_slot_is_not_blocked_and_has_no_diagnostics() -> None:
    bundle = ontology_bundle()
    constraints = load_scheduling_constraints(bundle)
    blocking = BlockingContext(
        {"prd_m": ["sub_m"]},
        {"sub_m": Substance(id="sub_m", name="Magnesium", kind=("mineral",))},
        compile_scheduling_constraint_execution_plans(
            constraints,
            {"sub_m": Substance(id="sub_m", name="Magnesium", kind=("mineral",))},
            bundle.runtime_program,
            allow_empty_selector_resolution=True,
        ),
    )
    slot_item_cases: tuple[dict[str, list[str]], ...] = ({}, {"breakfast": []})
    for slot_items in slot_item_cases:
        assert slot_is_blocked("prd_m", "breakfast", slot_items, blocking) is False
        assert blocking_constraint_diagnostics("prd_m", "breakfast", slot_items, blocking) == ()


def _bundle_with_vocabulary(bundle: OntologyBundle, vocabulary: dict[str, object]) -> OntologyBundle:
    return replace(bundle, decoded={**bundle.decoded, "runtime-vocabulary.yaml": vocabulary})
