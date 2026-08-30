"""Focused Cluster 3 checks for the canonical plan cutover."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import planner.engine.plan as plan_module
import pytest
from planner.contracts import Pillbox, Product, ProductComponent, Slot
from planner.engine._canonical_optimizer import CanonicalObjective, Optimal
from planner.engine._plan_active_index import ActiveIndexInput, build_active_index
from planner.engine._plan_types import ActiveIndex, PlanInputs
from planner.ontology.canonical_inference import Conflict, SameDimensionPressureConflict, Success
from planner.ontology.runtime_program import RuntimeCanonicalFactCatalog
from planner.paths import Paths
from planner.schedule_types import OptimalPublication


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        glue_contract=SimpleNamespace(inactive_stack_name="inactive"),
        canonical_laws=(),
    )


def _inputs(*, use_pattern: str | None = None) -> PlanInputs:
    slots = {
        "daily_food": Slot("daily_food", "Food", 1, (), "daily", "Daily", "daily", "with_food", None, None),
        "daily_empty": Slot("daily_empty", "Empty", 2, (), "daily", "Daily", "daily", "without_food", None, None),
        "training_pre": Slot("training_pre", "Pre", 1, (), "training", "Training", "training", None, None, "before"),
    }
    product = Product(
        "product", "Product", (ProductComponent("substance", id="cmp_product__substance"),), use_pattern=use_pattern
    )
    return PlanInputs(
        ontology_bundle=SimpleNamespace(),  # type: ignore[arg-type]
        runtime_program=_runtime(),  # type: ignore[arg-type]
        canonical_fact_catalog=RuntimeCanonicalFactCatalog((), (), (), (), (), (), ()),
        slots=slots,
        substances={},
        products={"product": product},
        global_relations=[],
        dashboard_files=[],
        stack_entries={"product": {"product": "product", "stack": "daily"}},
        pillboxes={
            "daily": Pillbox(
                "daily", "Daily", "daily", {key: value for key, value in slots.items() if value.stack == "daily"}
            ),
            "training": Pillbox("training", "Training", "training", {"training_pre": slots["training_pre"]}),
        },
    )


def test_cutover_constructs_exact_optimizer_input_without_legacy_state() -> None:
    inputs = _inputs()
    inputs.products["training_product"] = Product(
        "training_product",
        "Training Product",
        (ProductComponent("training_substance", id="cmp_training_product__training_substance"),),
    )
    inputs.stack_entries["training_product"] = {"product": "training_product", "stack": "training"}
    active = build_active_index(
        inputs.stack_entries,
        ActiveIndexInput(inputs.runtime_program, inputs.products, inputs.substances, inputs.canonical_fact_catalog, ()),
    )
    assert active is not None
    runtime = plan_module._PlanRuntime(inputs, active)
    optimizer_input = plan_module._canonical_optimizer_input(runtime)
    assert optimizer_input.item_domains == {"product": "daily", "training_product": "training"}
    assert set(optimizer_input.slots) == {"daily_food", "daily_empty", "training_pre"}
    assert not hasattr(inputs, "effect_scoring")
    assert not hasattr(inputs, "scheduling_constraint_plans")


def test_same_axis_conflict_is_layout_free_and_stops_before_optimizer(monkeypatch) -> None:
    inputs = _inputs()
    conflict = Conflict((SameDimensionPressureConflict("product", "meal_context", ("with_food", "without_food"), ()),))
    active = ActiveIndex(
        item_products={"product": "product"},
        active_components={"product": []},
        item_stacks={"product": "daily"},
        canonical_inference=conflict,
    )
    monkeypatch.setattr(plan_module, "build_active_index", lambda *_args, **_kwargs: active)
    monkeypatch.setattr(
        plan_module,
        "optimize_canonical_layout",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("optimizer called")),
    )
    result = plan_module._build_plan_runtime(Path("/tmp"), [], inputs)
    assert result.schedule_written is False
    assert result.status == "Indeterminate"
    assert "canonical_inference_conflict" in result.errors[0]


def test_not_every_day_is_an_ordinary_optimizer_item_with_presentation_grouping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(use_pattern="not_every_day")
    selected: list[dict[str, str]] = []

    def capture_selected(
        _catalog: RuntimeCanonicalFactCatalog,
        items: dict[str, str],
        _laws: tuple[object, ...],
    ) -> Success:
        selected.append(items)
        return Success(())

    monkeypatch.setattr(
        "planner.engine._plan_active_index.execute_canonical_inference",
        capture_selected,
    )
    active = build_active_index(
        inputs.stack_entries,
        ActiveIndexInput(inputs.runtime_program, inputs.products, inputs.substances, inputs.canonical_fact_catalog, ()),
    )
    assert active is not None
    assert active.item_stacks == {"product": "daily"}
    assert not hasattr(active, "not_every_day_items")
    assert selected == [{"product": "product"}]
    optimizer_input = plan_module._canonical_optimizer_input(plan_module._PlanRuntime(inputs, active))
    assert optimizer_input.item_domains == {"product": "daily"}
    assert optimizer_input.pressures == ()


def test_plan_has_no_legacy_search_import_or_compatibility_route() -> None:
    assert not hasattr(plan_module, "run_plan_search_result")
    assert not hasattr(plan_module, "_run_quarantined_legacy_search")
    assert not hasattr(plan_module, "build_stack_read_model")
    assert not hasattr(plan_module, "build_feasibility_index")


def test_successful_path_uses_canonical_publication_and_writer(monkeypatch, tmp_path: Path) -> None:
    inputs = _inputs()
    active = ActiveIndex(
        item_products={"product": "product"},
        active_components={"product": []},
        item_stacks={"product": "daily"},
        canonical_inference=Success(()),
    )
    monkeypatch.setattr(plan_module, "_checked_plan_inputs", lambda *_args: inputs)
    monkeypatch.setattr(plan_module, "build_active_index", lambda *_args, **_kwargs: active)
    result = Optimal(
        {"product": "daily_food"},
        CanonicalObjective(0, 1, ((1, "daily_food"),)),
        ("domain='daily' reachable_load_vectors=1",),
    )
    monkeypatch.setattr(plan_module, "optimize_canonical_layout", lambda *_args, **_kwargs: result)
    calls: list[object] = []
    monkeypatch.setattr(plan_module, "write_schedule_file", lambda _path, publication: calls.append(publication))
    output = plan_module._cmd_plan_inner(Paths.from_root(tmp_path), SimpleNamespace())
    assert output.status == "Optimal"
    assert output.schedule_written is True
    assert len(calls) == 1
    assert isinstance(calls[0], OptimalPublication)


def test_keyboard_interrupt_during_publication_is_indeterminate_and_does_not_write(monkeypatch, tmp_path: Path) -> None:
    inputs = _inputs()
    active = ActiveIndex(
        item_products={"product": "product"},
        active_components={"product": []},
        item_stacks={"product": "daily"},
        canonical_inference=Success(()),
    )
    runtime = plan_module._PlanRuntime(inputs, active)
    result = Optimal({"product": "daily_food"}, CanonicalObjective(0, 1, ((1, "daily_food"),)), ())
    monkeypatch.setattr(
        plan_module,
        "build_canonical_schedule_output",
        lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    writer_calls: list[object] = []
    monkeypatch.setattr(plan_module, "write_schedule_file", lambda *_args: writer_calls.append(True))
    output = plan_module._write_successful_plan(Paths.from_root(tmp_path), [], runtime, result)
    assert output.status == "Indeterminate"
    assert output.schedule_written is False
    assert writer_calls == []


def test_keyboard_interrupt_during_write_is_indeterminate(monkeypatch, tmp_path: Path) -> None:
    inputs = _inputs()
    active = ActiveIndex(
        item_products={"product": "product"},
        active_components={"product": []},
        item_stacks={"product": "daily"},
        canonical_inference=Success(()),
    )
    runtime = plan_module._PlanRuntime(inputs, active)
    result = Optimal({"product": "daily_food"}, CanonicalObjective(0, 1, ((1, "daily_food"),)), ())
    publication = SimpleNamespace(document={"pillboxes": {}})
    monkeypatch.setattr(plan_module, "build_canonical_schedule_output", lambda *_args: publication)
    monkeypatch.setattr(plan_module, "write_schedule_file", lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt))

    output = plan_module._write_successful_plan(Paths.from_root(tmp_path), [], runtime, result)

    assert output.status == "Indeterminate"
    assert output.schedule_written is False
