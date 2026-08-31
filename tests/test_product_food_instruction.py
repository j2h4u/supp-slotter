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
    instruction = next(fact for fact in runtime.canonical_scheduling.facts if fact.family == "ProductFoodInstruction")
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


def test_product_food_instructions_preserve_exact_product_provenance() -> None:
    runtime = _runtime()
    facts = {
        fact.subject.product: fact
        for fact in runtime.canonical_scheduling.facts
        if fact.family == "ProductFoodInstruction"
    }

    assert set(facts) == {"prd_932319251f", "prd_8eff2491b7", "prd_vitamealc8"}
    assert [(p.source, p.locator, p.quotation) for p in facts["prd_8eff2491b7"].provenance] == [
        (
            "src_biograce_vitamin_b5_instruction",
            "https://reestrinform.ru/reestr-sgr/reg-RU.77.99.88.003.R.000803.04.25.html",
            "Взрослым принимать по 1 таблетке в день во время еды",
        ),
    ]
    assert [(p.source, p.locator, p.quotation) for p in facts["prd_vitamealc8"].provenance] == [
        (
            "src_vitameal_vitamin_c_product",
            "https://vitameal.com/catalog/product-239/",
            "Взрослым по 1 капсуле в день во время еды",
        ),
        (
            "src_vitameal_vitamin_c_certificate",
            "https://vitameal.com/upload/certificate/%D0%92%D0%B8%D1%82.%D0%A1%20%D0%BA%D0%B0%D0%BF%D1%81%20%D1%81%D0%BE%D0%B4%D0%B8%D1%83%D0%BC.pdf",
            "Взрослым по 1 капсуле в день во время еды",
        ),
    ]
    assert all(fact.value == "take_with_food" for fact in facts.values())


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
    assert {proof.fact.id for proof in pressures[0].derivations if proof.family == "FoodEffect"} == {
        "fact_food_prd_w2s970gps4_sub_249199f726",
        "fact_food_prd_w2s970gps4_sub_646e568f61",
    }
