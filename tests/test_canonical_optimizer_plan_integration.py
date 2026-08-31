"""Planner integration checks for the solver-owned publication handoff."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import planner.engine.plan as plan_module
from planner.canonical_optimizer_result import CanonicalObjective, Optimal
from planner.contracts import Product, Slot
from planner.engine._plan_types import ActiveIndex
from planner.ontology.artifacts import load_ontology
from planner.ontology.canonical_inference import Success
from planner.paths import Paths
from planner.schedule_types import CanonicalPublicationSource, PublishedSchedule

ROOT = Path(__file__).resolve().parents[1]


def _runtime() -> plan_module._PlanRuntime:
    slot = Slot("slot", "Slot", 1, "daily", "Daily", "daily", {"meal": None})
    runtime_program = load_ontology(ROOT / "ontology").runtime_program
    inputs = SimpleNamespace(
        slots={"slot": slot},
        products={"prd": Product("prd", "Product", ())},
        runtime_program=SimpleNamespace(
            canonical_scheduling=SimpleNamespace(pressure_values_by_dimension={"meal": frozenset({"with_food"})}),
            engine_contract=runtime_program.engine_contract,
        ),
    )
    active = ActiveIndex({"item": "prd"}, {"item": "daily"}, Success(()))
    return plan_module._PlanRuntime(inputs, active)


def test_plan_hands_only_answer_free_source_to_writer(monkeypatch, tmp_path: Path) -> None:
    captured: list[CanonicalPublicationSource] = []
    optimal = Optimal({"item": "slot"}, CanonicalObjective(0, 1, ((1, "slot"),)), ())
    document = {"pillboxes": {"daily": {"label": "Daily", "slots": {"slot": {"label": "Slot", "products": []}}}}}

    def capture(_path: Path, source: CanonicalPublicationSource) -> PublishedSchedule:
        captured.append(source)
        return PublishedSchedule(document, optimal)  # type: ignore[arg-type]

    monkeypatch.setattr(plan_module, "write_schedule_file", capture)
    result = plan_module._publish_plan(Paths.from_root(tmp_path), [], _runtime())
    assert result.status == "Optimal"
    assert len(captured) == 1
    source = captured[0]
    assert source.item_domains == {"item": "daily"}
    assert not hasattr(plan_module, "optimize_canonical_layout")
    assert not hasattr(plan_module, "_canonical_optimizer_input")


def test_plan_result_has_no_dead_warning_field() -> None:
    assert "warnings" not in plan_module.PlanResult.__dataclass_fields__
