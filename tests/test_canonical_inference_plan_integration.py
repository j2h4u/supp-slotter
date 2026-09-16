"""Inference conflict handling at the plan/publication boundary."""

from __future__ import annotations

from types import SimpleNamespace

import planner.engine.plan as plan_module
from planner.engine._plan_types import ActiveIndex
from planner.engine.results import PlanResult
from planner.ontology.canonical_inference import Conflict, SameDimensionPressureConflict


def test_same_dimension_conflict_is_layout_free_and_never_reaches_writer(monkeypatch, capsys) -> None:
    conflict = Conflict((SameDimensionPressureConflict("item", "meal", ("with_food", "without_food"), ()),))
    active = ActiveIndex({"item": "prd"}, {"item": "daily"}, conflict)
    monkeypatch.setattr(plan_module, "build_active_index", lambda *_args, **_kwargs: active)
    inputs = SimpleNamespace(
        stack_entries={},
        products={},
        substances={},
        runtime_program=SimpleNamespace(),
        canonical_scheduling=SimpleNamespace(),
    )
    result = plan_module._build_plan_runtime(SimpleNamespace(), [], inputs)  # type: ignore[arg-type]
    assert isinstance(result, PlanResult)
    assert result.status == "Indeterminate"
    assert result.diagnostic is not None and result.diagnostic.code == "contradiction"
    assert not hasattr(plan_module, "optimize_canonical_layout")
    assert "plan: canonical_inference_conflict" in capsys.readouterr().err
