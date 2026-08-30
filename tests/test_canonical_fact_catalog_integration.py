"""Focused cross-card and plan-input integration checks for canonical facts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import planner.engine._plan_inputs as plan_inputs_module
import planner.engine.check as check_module
import pytest
from planner.contracts import CardLoadError, Product, ProductComponent, Substance
from planner.engine._plan_types import PlanInputs
from planner.ontology.canonical_facts import validate_canonical_fact_catalog
from planner.ontology.runtime_program import (
    RuntimeCanonicalFactCatalog,
    RuntimeCompositionRole,
    RuntimeEvidenceProvenance,
    RuntimeEvidenceSource,
    RuntimeFactSubject,
    RuntimeFoodEffect,
)
from planner.paths import Paths


def _catalog() -> RuntimeCanonicalFactCatalog:
    return RuntimeCanonicalFactCatalog(
        composition_roles=(RuntimeCompositionRole("cmp_prd_demo__sub_demo", "prd_demo", "sub_demo"),),
        evidence_sources=(RuntimeEvidenceSource("src_demo"),),
        food_effects=(
            RuntimeFoodEffect(
                "fact_food",
                RuntimeFactSubject("sub_demo", None),
                "cmp_prd_demo__sub_demo",
                (RuntimeEvidenceProvenance("src_demo", "paper#food", None),),
                "bioavailability_increases",
            ),
        ),
        acute_alertness_effects=(),
        acute_sleep_effects=(),
        pre_exercise_performance_effects=(),
        post_exercise_recovery_effects=(),
    )


def _cards() -> tuple[dict[str, Substance], dict[str, Product]]:
    substances = {"sub_demo": Substance("sub_demo", "Demo substance")}
    products = {
        "prd_demo": Product(
            "prd_demo",
            "Demo product",
            components=(ProductComponent("sub_demo", id="cmp_prd_demo__sub_demo"),),
        ),
    }
    return substances, products


def test_canonical_reference_validator_accepts_empty_catalog() -> None:
    validate_canonical_fact_catalog(
        RuntimeCanonicalFactCatalog((), (), (), (), (), (), ()),
        {},
        {},
    )


def test_canonical_reference_validator_accepts_matching_role_and_fact() -> None:
    substances, products = _cards()
    validate_canonical_fact_catalog(_catalog(), substances, products)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_product",
        "unknown_substance",
        "missing_component",
        "mismatched_component_id",
        "unknown_subject",
        "unknown_applicability",
        "mismatched_subject",
        "mismatched_role_id",
        "unknown_source",
        "mismatched_subject_role",
    ],
)
def test_canonical_reference_validator_rejects_dangling_or_inconsistent_references(  # noqa: C901
    mutation: str,
) -> None:
    substances, products = _cards()
    catalog = _catalog()
    if mutation == "unknown_product":
        role = replace(catalog.composition_roles[0], product="prd_missing")
        catalog = replace(catalog, composition_roles=(role,))
    elif mutation == "unknown_substance":
        role = replace(catalog.composition_roles[0], substance="sub_missing")
        catalog = replace(catalog, composition_roles=(role,))
    elif mutation == "missing_component":
        products = {"prd_demo": replace(products["prd_demo"], components=())}
    elif mutation == "mismatched_component_id":
        products = {
            "prd_demo": replace(
                products["prd_demo"],
                components=(ProductComponent("sub_demo", id="cmp_wrong__sub_demo"),),
            )
        }
    elif mutation == "unknown_subject":
        fact = replace(catalog.food_effects[0], subject=RuntimeFactSubject("sub_missing", None))
        catalog = replace(catalog, food_effects=(fact,))
    elif mutation == "unknown_applicability":
        fact = replace(catalog.food_effects[0], applicability="cmp_missing")
        catalog = replace(catalog, food_effects=(fact,))
    elif mutation == "mismatched_subject":
        substances["sub_other"] = Substance("sub_other", "Other substance")
        fact = replace(catalog.food_effects[0], subject=RuntimeFactSubject("sub_other", None))
        catalog = replace(catalog, food_effects=(fact,))
    elif mutation == "mismatched_role_id":
        role = replace(catalog.composition_roles[0], id="cmp_other__sub_demo")
        catalog = replace(catalog, composition_roles=(role,))
    elif mutation == "unknown_source":
        fact = replace(
            catalog.food_effects[0],
            provenance=(RuntimeEvidenceProvenance("src_missing", "paper#food", None),),
        )
        catalog = replace(catalog, food_effects=(fact,))
    elif mutation == "mismatched_subject_role":
        catalog = replace(
            catalog,
            composition_roles=(*catalog.composition_roles, RuntimeCompositionRole("cmp_other", "prd_demo", "sub_demo")),
            food_effects=(replace(catalog.food_effects[0], subject=RuntimeFactSubject(None, "cmp_other")),),
        )

    with pytest.raises(CardLoadError, match="canonical fact catalog reference validation failed"):
        validate_canonical_fact_catalog(catalog, substances, products)


def test_plan_inputs_carries_verified_canonical_catalog(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    substances, products = _cards()
    catalog = _catalog()
    runtime = SimpleNamespace(canonical_fact_catalog=catalog, effect_scoring=object())
    bundle = SimpleNamespace(runtime_program=runtime)
    monkeypatch.setattr(plan_inputs_module, "load_pillboxes", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "check_pillbox_slot_anchors", lambda *_args: [])
    monkeypatch.setattr(plan_inputs_module, "load_scheduling_policies", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "load_yaml", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "flatten_pillbox_slots", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "load_substance_registry", lambda *_args: substances)
    monkeypatch.setattr(plan_inputs_module, "load_product_registry", lambda *_args: products)
    monkeypatch.setattr(plan_inputs_module, "load_global_relations", lambda *_args: [])
    monkeypatch.setattr(plan_inputs_module, "normalize_stack_entries", lambda *_args: {})
    monkeypatch.setattr(plan_inputs_module, "load_scheduling_constraints", lambda *_args: ())
    monkeypatch.setattr(
        plan_inputs_module, "compile_scheduling_constraint_execution_plans", lambda *_args, **_kwargs: ()
    )

    result = plan_inputs_module.load_plan_inputs(Paths.from_root(tmp_path), bundle)  # type: ignore[arg-type]

    assert isinstance(result, PlanInputs)
    assert result.canonical_fact_catalog is catalog


def test_check_uses_the_same_canonical_reference_validator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    substances, products = _cards()
    catalog = _catalog()
    runtime = SimpleNamespace(canonical_fact_catalog=catalog)
    bundle = SimpleNamespace(runtime_program=runtime)
    calls: list[tuple[object, object, object]] = []
    monkeypatch.setattr(check_module, "load_scheduling_policies", lambda *_args: {})
    monkeypatch.setattr(check_module, "check_substances", lambda *_args: ([], [], set(substances)))
    monkeypatch.setattr(check_module, "load_substance_registry", lambda *_args: substances)
    monkeypatch.setattr(check_module, "load_yaml", lambda *_args: {})
    monkeypatch.setattr(check_module, "check_global_relations", lambda *_args: [])
    monkeypatch.setattr(check_module, "check_product_formulas", lambda *_args: ([], [], set(products)))
    monkeypatch.setattr(check_module, "load_product_registry", lambda *_args: products)
    monkeypatch.setattr(check_module, "validate_stacks", lambda *_args: ([], []))
    monkeypatch.setattr(check_module, "check_dashboards", lambda *_args: [])
    monkeypatch.setattr(
        check_module,
        "validate_canonical_fact_catalog",
        lambda actual, actual_substances, actual_products: calls.append((actual, actual_substances, actual_products)),
    )

    check_module._extend_card_validation_errors(Paths.from_root(tmp_path), [], [], bundle)  # type: ignore[arg-type]

    assert calls == [(catalog, substances, products)]
