"""Plan-boundary checks for canonical pressure inference."""

from __future__ import annotations

from types import SimpleNamespace

import planner.engine.plan as plan_module
from planner.canonical_optimizer_result import Diagnostic
from planner.contracts import Product, ProductComponent, Slot, Substance
from planner.engine._canonical_optimizer import CanonicalOptimizerInput, Indeterminate
from planner.engine._plan_active_index import ActiveIndexInput, build_active_index
from planner.engine._plan_types import ActiveIndex
from planner.engine.results import PlanResult
from planner.ontology.canonical_inference import (
    Conflict,
    SameDimensionPressureConflict,
    Success,
    execute_canonical_inference,
)
from planner.ontology.runtime_program import (
    RuntimeCanonicalFactCatalog,
    RuntimeCanonicalLaw,
    RuntimeCompositionRole,
    RuntimeEvidenceProvenance,
    RuntimeEvidenceSource,
    RuntimeFactApplicability,
    RuntimeFactSubject,
    RuntimeFoodEffect,
)


def _canonical_fixture() -> tuple[RuntimeCanonicalFactCatalog, tuple[RuntimeCanonicalLaw, ...]]:
    catalog = RuntimeCanonicalFactCatalog(
        evidence_sources=(RuntimeEvidenceSource("src_demo"),),
        food_effects=(
            RuntimeFoodEffect(
                "fact_food",
                RuntimeFactSubject("sub_demo", None),
                RuntimeFactApplicability("sub_demo", None),
                (RuntimeEvidenceProvenance("src_demo", "paper#food", "food evidence"),),
                "bioavailability_increases",
            ),
        ),
        acute_alertness_effects=(),
        acute_sleep_effects=(),
        pre_exercise_performance_effects=(),
        post_exercise_recovery_effects=(),
    )
    laws = (
        RuntimeCanonicalLaw(
            "law_food_bioavailability_increases",
            "FoodEffect",
            "bioavailability_increases",
            "meal_context",
            "with_food",
        ),
    )
    return catalog, laws


def test_canonical_facts_alone_derive_pressure_without_schedule_answers() -> None:
    catalog, laws = _canonical_fixture()

    result = execute_canonical_inference(
        catalog,
        {"item_demo": "prd_demo"},
        laws,
        composition_roles=(
            RuntimeCompositionRole(id="cmp_prd_demo__sub_demo", product="prd_demo", substance="sub_demo"),
        ),
    )

    assert isinstance(result, Success)
    assert [(pressure.item_id, pressure.dimension, pressure.value) for pressure in result.pressures] == [
        ("item_demo", "meal_context", "with_food"),
    ]
    assert result.pressures[0].derivations[0].fact_id == "fact_food"
    assert result.pressures[0].derivations[0].law_id == "law_food_bioavailability_increases"


def test_active_index_attaches_canonical_result_after_product_resolution() -> None:
    catalog, laws = _canonical_fixture()
    runtime_program = SimpleNamespace(
        glue_contract=SimpleNamespace(
            inactive_stack_name="inactive",
            stack_partition=SimpleNamespace(routable_stack_names=("daily", "training")),
        )
    )
    products = {
        "prd_demo": Product(
            "prd_demo",
            "Demo",
            components=(ProductComponent("sub_demo", id="cmp_prd_demo__sub_demo"),),
        )
    }

    active = build_active_index(
        {"item_demo": {"product": "prd_demo", "stack": "daily"}},
        ActiveIndexInput(
            runtime_program=runtime_program,  # type: ignore[arg-type]
            products=products,
            substances={"sub_demo": Substance("sub_demo", "Demo")},
            canonical_fact_catalog=catalog,
            canonical_laws=laws,
        ),
    )

    assert isinstance(active.canonical_inference, Success)
    assert active.canonical_inference.pressures[0].identity.item_id == "item_demo"


def _active_index_with_inference(inference: object) -> ActiveIndex:
    return ActiveIndex(
        item_products={"item_demo": "prd_demo"},
        item_stacks={"item_demo": "daily"},
        canonical_inference=inference,  # type: ignore[arg-type]
    )


def test_same_dimension_conflict_stops_before_optimizer(monkeypatch) -> None:
    conflict = Conflict((
        SameDimensionPressureConflict(
            "item_demo",
            "meal_context",
            ("with_food", "without_food"),
            (),
        ),
    ))
    active = _active_index_with_inference(conflict)
    monkeypatch.setattr(plan_module, "build_active_index", lambda *_args, **_kwargs: active)
    inputs = SimpleNamespace(
        stack_entries={},
        products={},
        substances={},
        runtime_program=SimpleNamespace(canonical_laws=()),
        canonical_fact_catalog=RuntimeCanonicalFactCatalog((), (), (), (), (), ()),
    )

    result = plan_module._build_plan_runtime(SimpleNamespace(), [], inputs)  # type: ignore[arg-type]

    assert isinstance(result, PlanResult)
    assert result.exit_code == 1
    assert result.schedule_written is False
    assert result.errors == [
        "plan: canonical_inference_conflict item_id='item_demo' "
        "dimension='meal_context' values=(with_food,without_food)"
    ]


def test_conflict_free_inference_routes_only_to_exact_optimizer(monkeypatch) -> None:
    runtime = plan_module._PlanRuntime(
        SimpleNamespace(
            slots={"food": Slot("food", "Food", 1, "daily", "Daily", "daily", "with_food", None, None)},
        ),
        _active_index_with_inference(Success(())),
    )
    captured: list[CanonicalOptimizerInput] = []

    def indeterminate(optimizer_input: CanonicalOptimizerInput) -> Indeterminate:
        captured.append(optimizer_input)
        return Indeterminate(Diagnostic("interrupted", "interrupted"))

    monkeypatch.setattr(plan_module, "optimize_canonical_layout", indeterminate)

    result = plan_module._run_successful_plan_search([], runtime)

    assert isinstance(result, PlanResult)
    assert result.status == "Indeterminate"
    assert captured[0].item_domains == {"item_demo": "daily"}
    assert not hasattr(plan_module, "_run_quarantined_legacy_search")
