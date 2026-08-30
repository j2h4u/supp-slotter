"""V-right checks for the solver-owned canonical publication boundary."""

from __future__ import annotations

import inspect
from pathlib import Path

import planner.canonical_optimizer as optimizer_module
import planner.schedule_writer as schedule_writer
import pytest
from planner.canonical_optimizer_result import Indeterminate, Optimal
from planner.contracts import Product, ProductComponent, Slot
from planner.ontology.canonical_inference import (
    CompositionApplicabilityPath,
    NormalizedUnaryPressure,
    PressureDerivation,
    Success,
    UnaryPressureIdentity,
)
from planner.ontology.runtime_program import (
    IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY,
    RuntimeCanonicalLaw,
    RuntimeCanonicalSchedulingFact,
    RuntimeEvidenceProvenance,
    RuntimeFactApplicability,
    RuntimeFactSubject,
)
from planner.schedule_types import CanonicalPublicationSource
from planner.schedule_writer import write_schedule_file


def _slot(slot_id: str, order: int, anchor: str | None = None) -> Slot:
    return Slot(slot_id, slot_id, order, "daily", "Daily", "daily", {"meal": anchor})


def _source(*, anchors: tuple[str | None, str | None] = (None, None)) -> CanonicalPublicationSource:
    product_a = Product("prd_a", "Alpha", (ProductComponent("sub_a", "cmp_a"),))
    product_b = Product("prd_b", "Beta", (ProductComponent("sub_b", "cmp_b"),), use_pattern="not_every_day")
    return CanonicalPublicationSource(
        item_products={"item_a": "prd_a", "item_b": "prd_b"},
        item_domains={"item_a": "daily", "item_b": "daily"},
        slots={"first": _slot("first", 1, anchors[0]), "second": _slot("second", 2, anchors[1])},
        inference=Success(()),
        products={"prd_a": product_a, "prd_b": product_b},
        pressure_values_by_dimension={"meal": frozenset({"with_food", "without_food"})},
        pressure_satisfaction_strategy=IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY,
    )


def _pressure(item_id: str, dimension: str, value: str) -> NormalizedUnaryPressure:
    subject = RuntimeFactSubject("sub_a", None)
    law = RuntimeCanonicalLaw(f"law_{dimension}", "FoodEffect", "effect", dimension, value)
    fact = RuntimeCanonicalSchedulingFact(
        f"fact_{dimension}",
        "FoodEffect",
        subject,
        RuntimeFactApplicability("sub_a", None),
        (RuntimeEvidenceProvenance("source", f"locator#{dimension}", None),),
        "effect",
    )
    derivation = PressureDerivation(
        law,
        "FoodEffect",
        fact,
        "effect",
        subject,
        CompositionApplicabilityPath("substance", "sub_a", "cmp_a", "prd_a", "sub_a"),
        fact.provenance,
    )
    return NormalizedUnaryPressure(UnaryPressureIdentity(item_id, dimension, value), (derivation,))


def _single_item_pressure_source(
    pressures: tuple[NormalizedUnaryPressure, ...], anchors: dict[str, str | None]
) -> CanonicalPublicationSource:
    return CanonicalPublicationSource(
        item_products={"item_a": "prd_a"},
        item_domains={"item_a": "daily"},
        slots={"only": Slot("only", "Only", 1, "daily", "Daily", "daily", anchors)},
        inference=Success(pressures),
        products={"prd_a": Product("prd_a", "Alpha", ())},
        pressure_values_by_dimension={key: frozenset({"wanted", "other"}) for key in anchors},
        pressure_satisfaction_strategy=IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY,
    )


def test_writer_owns_exact_solve_and_projects_two_items_with_squared_load_two(tmp_path: Path) -> None:
    published = write_schedule_file(tmp_path / "schedule.yaml", _source())

    assert not isinstance(published, Indeterminate)
    assert published.result.objective.squared_load == 2
    assert published.document["summary"]["placement_groups"] == {
        "routine": ["item_a"],
        "episodic": ["item_b"],
    }
    product_entries = [
        product
        for pillbox in published.document["pillboxes"].values()
        for slot in pillbox["slots"].values()
        for product in slot["products"]
    ]
    assert product_entries == [{"item_id": "item_a", "label": "Alpha"}, {"item_id": "item_b", "label": "Beta"}]


def test_writer_calls_exact_optimizer_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    real_optimize = optimizer_module.optimize_canonical_layout
    calls = 0

    def counted(*args: object, **kwargs: object) -> Optimal | Indeterminate:
        nonlocal calls
        calls += 1
        return real_optimize(*args, **kwargs)

    monkeypatch.setattr(optimizer_module, "optimize_canonical_layout", counted)
    assert not isinstance(write_schedule_file(tmp_path / "schedule.yaml", _source()), Indeterminate)
    assert calls == 1


def test_snapshot_is_immutable_after_source_input_mutation(tmp_path: Path) -> None:
    item_products = {"item_a": "prd_a", "item_b": "prd_b"}
    item_domains = {"item_a": "daily", "item_b": "daily"}
    slots = {"first": _slot("first", 1), "second": _slot("second", 2)}
    products = {
        "prd_a": Product("prd_a", "Alpha", ()),
        "prd_b": Product("prd_b", "Beta", ()),
    }
    source = CanonicalPublicationSource(
        item_products,
        item_domains,
        slots,
        Success(()),
        products,
        {"meal": frozenset({"with_food", "without_food"})},
        IMPLEMENTED_PRESSURE_SATISFACTION_STRATEGY,
    )
    item_products["item_a"] = "prd_b"
    item_domains["item_a"] = "other"
    slots["first"] = _slot("first", 1, "with_food")
    products["prd_a"] = Product("prd_a", "Mutated", ())
    published = write_schedule_file(tmp_path / "schedule.yaml", source)
    assert not isinstance(published, Indeterminate)
    assert published.document["pillboxes"]["daily"]["slots"]["first"]["products"][0]["label"] == "Alpha"


def test_unsatisfied_pressure_keeps_match_but_uses_balance_only_basis(tmp_path: Path) -> None:
    source = _single_item_pressure_source((_pressure("item_a", "meal", "wanted"),), {"meal": "other"})
    published = write_schedule_file(tmp_path / "schedule.yaml", source)
    assert not isinstance(published, Indeterminate)
    explanation = published.document["canonical_explanations"]["item_a"]
    assert explanation["placement_basis"] == "balance_and_tie_break_only"
    assert explanation["pressure_matches"][0]["satisfied"] is False


def test_any_satisfied_match_makes_mixed_evidence_pressure_basis(tmp_path: Path) -> None:
    source = _single_item_pressure_source(
        (_pressure("item_a", "meal", "wanted"), _pressure("item_a", "timing", "wanted")),
        {"meal": "wanted", "timing": "other"},
    )
    published = write_schedule_file(tmp_path / "schedule.yaml", source)
    assert not isinstance(published, Indeterminate)
    matches = published.document["canonical_explanations"]["item_a"]["pressure_matches"]
    assert published.document["canonical_explanations"]["item_a"]["placement_basis"] == "pressure_evidence"
    assert [match["satisfied"] for match in matches] == [True, False]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"item_products": {"item_a": "missing"}, "item_domains": {"item_a": "daily"}},
        {"item_products": {"item_a": "prd_a"}, "item_domains": {"other": "daily"}},
        {"slots": {"wrong": _slot("first", 1)}},
    ],
)
def test_invalid_source_mapping_product_domain_or_slot_publishes_nothing(
    tmp_path: Path, kwargs: dict[str, object]
) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("stale", encoding="utf-8")
    source = _source()
    values = {
        "item_products": source.item_products,
        "item_domains": source.item_domains,
        "slots": source.slots,
        "inference": source.inference,
        "products": source.products,
        "pressure_values_by_dimension": source.pressure_values_by_dimension,
    }
    values.update(kwargs)
    with pytest.raises((TypeError, ValueError)):
        CanonicalPublicationSource(**values)  # type: ignore[arg-type]
    assert target.read_text(encoding="utf-8") == "stale"


def test_writer_does_not_accept_forged_projection_or_precomputed_optimal(tmp_path: Path) -> None:
    signature = inspect.signature(write_schedule_file)
    assert set(signature.parameters) == {"schedule_file", "source"}
    forged = write_schedule_file(tmp_path / "schedule.yaml", {"document": {}, "result": object()})  # type: ignore[arg-type]
    assert isinstance(forged, Indeterminate)
    assert not (tmp_path / "schedule.yaml").exists()


@pytest.mark.parametrize("error", [OSError("fsync failed"), KeyboardInterrupt()])
def test_failed_or_interrupted_write_removes_stale_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("stale", encoding="utf-8")
    monkeypatch.setattr(schedule_writer.os, "fsync", lambda _fd: (_ for _ in ()).throw(error))
    if isinstance(error, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            write_schedule_file(target, _source())
    else:
        assert isinstance(write_schedule_file(target, _source()), Indeterminate)
    assert not target.exists()
    assert not list(tmp_path.glob("schedule.yaml.tmp.*"))
