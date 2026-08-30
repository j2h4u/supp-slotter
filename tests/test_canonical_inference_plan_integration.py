"""Plan-boundary checks for canonical pressure inference.

These tests deliberately stop at the Cluster 2 boundary: canonical proofs are
attached to the active index and conflicts fail before legacy feasibility/search,
while conflict-free inputs are still sent through the quarantined optimizer.
"""

from __future__ import annotations

from types import SimpleNamespace

import planner.engine._plan_active_index as active_index_module
import planner.engine.plan as plan_module
from planner.contracts import Product, ProductComponent, Substance
from planner.engine._plan_active_index import ActiveIndexInput, build_active_index
from planner.engine._plan_feasibility import FeasibilityIndex
from planner.engine._plan_search import PlanSearchResult
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
    RuntimeFactSubject,
    RuntimeFoodEffect,
)


def _canonical_fixture() -> tuple[RuntimeCanonicalFactCatalog, tuple[RuntimeCanonicalLaw, ...]]:
    role_id = "cmp_prd_demo__sub_demo"
    catalog = RuntimeCanonicalFactCatalog(
        composition_roles=(RuntimeCompositionRole(role_id, "prd_demo", "sub_demo"),),
        evidence_sources=(RuntimeEvidenceSource("src_demo"),),
        food_effects=(
            RuntimeFoodEffect(
                "fact_food",
                RuntimeFactSubject("sub_demo", None),
                role_id,
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

    result = execute_canonical_inference(catalog, {"item_demo": "prd_demo"}, laws)

    assert isinstance(result, Success)
    assert [(pressure.item_id, pressure.dimension, pressure.value) for pressure in result.pressures] == [
        ("item_demo", "meal_context", "with_food"),
    ]
    assert result.pressures[0].derivations[0].fact_id == "fact_food"
    assert result.pressures[0].derivations[0].law_id == "law_food_bioavailability_increases"
    assert Substance("sub_demo", "Demo").schedule_assertions == ()


def test_active_index_attaches_canonical_result_after_product_resolution(monkeypatch) -> None:
    catalog, laws = _canonical_fixture()
    monkeypatch.setattr(active_index_module, "project_schedule_assignments", lambda *_args: SimpleNamespace(groups=()))
    read_model = SimpleNamespace(
        collect_intra_product_scheduling_constraint_conflicts=lambda **_kwargs: [],
    )
    runtime_program = SimpleNamespace(glue_contract=SimpleNamespace(inactive_stack_name="inactive"))
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
            policies={},
            read_model=read_model,  # type: ignore[arg-type]
            scheduling_constraint_plans=(),
            canonical_fact_catalog=catalog,
            canonical_laws=laws,
        ),
        {},
        [],
    )

    assert active is not None
    assert isinstance(active.canonical_inference, Success)
    assert active.canonical_inference.pressures[0].identity.item_id == "item_demo"


def _active_index_with_inference(
    inference: object,
) -> ActiveIndex:
    return ActiveIndex(
        item_products={"item_demo": "prd_demo"},
        active_components={"item_demo": ["sub_demo"]},
        intra_product_relation_conflicts_by_item={"item_demo": []},
        item_stacks={"item_demo": "daily"},
        schedule_projection_by_item={"item_demo": SimpleNamespace(groups=())},  # type: ignore[arg-type]
        active_policy_ids_by_item={"item_demo": set()},
        canonical_inference=inference,  # type: ignore[arg-type]
    )


def test_same_dimension_conflict_stops_before_feasibility_and_search(
    monkeypatch,
    tmp_path,
) -> None:
    conflict = Conflict((
        SameDimensionPressureConflict(
            "item_demo",
            "meal_context",
            ("with_food", "without_food"),
            (),
        ),
    ))
    active = _active_index_with_inference(conflict)
    monkeypatch.setattr(plan_module, "build_stack_read_model", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(plan_module, "build_active_index", lambda *_args, **_kwargs: active)
    monkeypatch.setattr(
        plan_module,
        "build_feasibility_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("feasibility must not run")),
    )
    inputs = SimpleNamespace(
        slots={},
        substances={},
        global_relations=[],
        products={},
        ontology_bundle=SimpleNamespace(),
        policies={},
        scheduling_constraints=(),
        scheduling_constraint_plans=(),
        stack_entries={},
        runtime_program=SimpleNamespace(canonical_laws=()),
        canonical_fact_catalog=RuntimeCanonicalFactCatalog((), (), (), (), (), (), ()),
    )

    result = plan_module._build_plan_runtime(plan_module.Paths.from_root(tmp_path), [], inputs)  # type: ignore[arg-type]

    assert isinstance(result, PlanResult)
    assert result.exit_code == 1
    assert result.schedule_written is False
    assert result.errors == [
        "plan: canonical_inference_conflict item_id='item_demo' "
        "dimension='meal_context' values=(with_food,without_food)"
    ]


def test_conflict_free_inference_explicitly_routes_to_quarantined_legacy_optimizer(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        plan_module,
        "run_plan_search_result",
        lambda search_input: captured.append(search_input) or PlanSearchResult({}, (0.0, 0, 0, 0.0), {}),
    )
    runtime = SimpleNamespace(
        inputs=SimpleNamespace(
            slots={},
            substances={},
            effect_scoring=object(),
            scheduling_constraint_plans=(),
            runtime_program=object(),
        ),
        active=_active_index_with_inference(Success(())),
        prefer_pairs=set(),
        feasibility=FeasibilityIndex({}, {}, [], [], []),
    )

    result = plan_module._run_successful_plan_search([], runtime)  # type: ignore[arg-type]

    assert result.assignment == {}
    assert len(captured) == 1
    assert not hasattr(captured[0], "canonical_inference")
