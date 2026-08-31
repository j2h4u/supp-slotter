"""Focused acceptance for product-only food instructions and role deduplication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from planner.ontology.canonical_inference import Success, execute_canonical_inference
from planner.ontology.runtime_program import (
    IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
    RuntimeCompositionRole,
    decode_runtime_program,
)

ROOT = Path(__file__).resolve().parents[1]


def _runtime():
    payload = cast(
        dict[str, Any],
        json.loads((ROOT / "ontology/generated/runtime-program.json").read_text(encoding="utf-8")),
    )
    return decode_runtime_program(payload)


def test_product_food_instruction_targets_intake_item_without_component_fanout() -> None:
    runtime = _runtime()
    product = "prd_932319251f"
    instruction = next(
        fact for fact in runtime.canonical_scheduling.facts if fact.family == "ProductFoodInstruction"
    )
    assert instruction.applicability.target_kind == "product"
    roles = (RuntimeCompositionRole("cmp_component", product, "sub_component"),)

    result = execute_canonical_inference(
        runtime.canonical_scheduling,
        {"intake": product},
        applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
        composition_roles=roles,
        known_products=(product,),
    )

    assert isinstance(result, Success)
    pressure = next(row for row in result.pressures if row.value == "with_food")
    assert pressure.item_id == "intake"
    proof = next(row for row in pressure.derivations if row.family == "ProductFoodInstruction")
    assert proof.path.target_kind == "product"
    assert proof.path.target_id == product


def test_psalae_role_facts_normalize_to_one_pressure_with_both_proofs() -> None:
    runtime = _runtime()
    product = "prd_w2s970gps4"
    roles = (
        RuntimeCompositionRole("cmp_prd_w2s970gps4__sub_249199f726", product, "sub_249199f726"),
        RuntimeCompositionRole("cmp_prd_w2s970gps4__sub_646e568f61", product, "sub_646e568f61"),
    )

    result = execute_canonical_inference(
        runtime.canonical_scheduling,
        {"intake": product},
        applicability_expansion_strategy=IMPLEMENTED_APPLICABILITY_EXPANSION_STRATEGY,
        composition_roles=roles,
        known_products=(product,),
    )

    assert isinstance(result, Success)
    pressures = [row for row in result.pressures if row.item_id == "intake" and row.value == "with_food"]
    assert len(pressures) == 1
    assert {
        proof.fact.id
        for proof in pressures[0].derivations
        if proof.family == "FoodEffect"
    } == {
        "fact_food_prd_w2s970gps4_sub_249199f726",
        "fact_food_prd_w2s970gps4_sub_646e568f61",
    }
