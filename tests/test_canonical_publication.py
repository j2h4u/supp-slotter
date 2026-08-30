"""Focused V-right checks for the closed canonical publication boundary."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import planner.engine.plan as plan_module
import pytest
from planner.canonical_optimizer_result import Diagnostic
from planner.contracts import MealContext, Product, ProductComponent, Slot
from planner.engine._canonical_optimizer import Indeterminate, Optimal, optimize_canonical_layout
from planner.engine._plan_output import CanonicalScheduleOutputInput, build_canonical_schedule_output
from planner.engine.show import cmd_show
from planner.ontology.canonical_inference import Success, UnaryPressureIdentity
from planner.ontology.errors import OntologyInfrastructureError
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
from planner.schedule_types import OptimalPublication
from planner.schedule_writer import write_schedule_file


def _slot(slot_id: str, order: int, *, meal: str | None = None) -> Slot:
    return Slot(
        slot_id,
        slot_id,
        order,
        "daily",
        "daily",
        "daily",
        cast(MealContext | None, meal),
        None,
        None,
    )


def _inference() -> Success:
    role = RuntimeCompositionRole("cmp_prd_demo__sub_demo", "prd_demo", "sub_demo")
    catalog = RuntimeCanonicalFactCatalog(
        evidence_sources=(RuntimeEvidenceSource("src_demo"),),
        food_effects=(
            RuntimeFoodEffect(
                "fact_food",
                RuntimeFactSubject("sub_demo", None),
                RuntimeFactApplicability("sub_demo", None),
                (RuntimeEvidenceProvenance("src_demo", "paper#demo", "quote"),),
                "bioavailability_increases",
            ),
        ),
        acute_alertness_effects=(),
        acute_sleep_effects=(),
        pre_exercise_performance_effects=(),
        post_exercise_recovery_effects=(),
    )
    law = RuntimeCanonicalLaw(
        "law_food",
        "FoodEffect",
        "bioavailability_increases",
        "meal_context",
        "with_food",
    )
    from planner.ontology.canonical_inference import execute_canonical_inference

    result = execute_canonical_inference(catalog, {"item_demo": "prd_demo"}, (law,), composition_roles=(role,))
    assert isinstance(result, Success)
    return result


def _publication() -> OptimalPublication:
    slots = {"plain": _slot("plain", 1), "food": _slot("food", 2, meal="with_food")}
    result = optimize_canonical_layout(
        {"item_demo": "daily"},
        slots,
        (UnaryPressureIdentity("item_demo", "meal_context", "with_food"),),
    )
    assert isinstance(result, Optimal)
    return build_canonical_schedule_output(
        CanonicalScheduleOutputInput(
            result=result,
            slots=slots,
            inference=_inference(),
            item_products={"item_demo": "prd_demo"},
        )
    )


def test_canonical_document_contains_typed_proofs_and_no_legacy_explanations() -> None:
    publication = _publication()
    document = cast(dict[str, object], publication.document)
    assert document["status"] == "Optimal"
    objective = cast(dict[str, object], document["objective"])
    assert objective["satisfied_pressures"] == 1
    assert document["assignments"] == {"item_demo": "food"}
    match = cast(list[dict[str, object]], document["pressure_matches"])[0]
    assert match["satisfied"] is True
    assert match["fact_ids"] == ["fact_food"]
    assert match["law_ids"] == ["law_food"]
    assert match["applicability_role_ids"] == ["cmp_prd_demo__sub_demo"]
    assert match["provenance_refs"] == [{"source": "src_demo", "locator": "paper#demo", "quotation": "quote"}]
    assert "pairwise_journal" not in document
    assert "explanations" not in document
    assert "policy_contributions" not in document
    assert "advisory_penalty" not in document
    assert "advisory_constraint_ids" not in document
    assert "canonical_explanations" in document
    domain_loads = cast(dict[str, dict[str, object]], document["domain_loads"])
    assert domain_loads["daily"]["proof"]


def test_not_every_day_is_a_presentation_group_for_the_proved_assignment() -> None:
    slots = {"plain": _slot("plain", 1), "food": _slot("food", 2, meal="with_food")}
    result = optimize_canonical_layout(
        {"item_demo": "daily"},
        slots,
        (UnaryPressureIdentity("item_demo", "meal_context", "with_food"),),
    )
    assert isinstance(result, Optimal)
    product = Product(
        "prd_demo", "Demo", (ProductComponent("sub_demo", "cmp_prd_demo__sub_demo"),), use_pattern="not_every_day"
    )
    publication = build_canonical_schedule_output(
        CanonicalScheduleOutputInput(
            result=result,
            slots=slots,
            inference=_inference(),
            item_products={"item_demo": "prd_demo"},
            item_stacks={"item_demo": "daily"},
            products={"prd_demo": product},
        )
    )

    document = cast(dict[str, object], publication.document)
    summary = cast(dict[str, object], document["summary"])
    groups = cast(dict[str, list[str]], summary["placement_groups"])
    pillboxes = cast(dict[str, dict[str, object]], document["pillboxes"])
    slots_out = cast(dict[str, dict[str, object]], pillboxes["daily"]["slots"])
    assert groups == {"routine": [], "episodic": ["Demo"]}
    assert slots_out["food"]["products"] == ["Demo"]
    assert slots_out["plain"]["products"] == []


def test_publication_boundary_refuses_indeterminate_and_legacy_documents(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    indeterminate = Indeterminate(Diagnostic("timeout", "timeout"))
    with pytest.raises(TypeError, match="only an Optimal"):
        OptimalPublication(indeterminate, _inference(), {}, {})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="OptimalPublication"):
        write_schedule_file(target, {})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-canonical fields"):
        OptimalPublication(  # type: ignore[arg-type]
            _publication().result,
            _inference(),
            {},
            {"status": "Optimal", "assignments": {}, "pairwise_journal": []},
        )


@pytest.mark.parametrize("error", [OSError("simulated write failure"), KeyboardInterrupt()])
def test_atomic_write_failure_invalidates_current_document_and_cleans_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("pre-existing schedule\n", encoding="utf-8")

    def fail_fsync(_fd: int) -> None:
        raise error

    import planner.schedule_writer as schedule_writer

    monkeypatch.setattr(schedule_writer.os, "fsync", fail_fsync)
    with pytest.raises(type(error)):
        write_schedule_file(target, _publication())
    assert not target.exists()
    assert list(tmp_path.glob("schedule.yaml.tmp.*")) == []


def test_writer_revalidation_failure_invalidates_current_document(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("pre-existing schedule\n", encoding="utf-8")
    publication = _publication()
    publication.document["pressure_matches"][0]["law_ids"] = ["law_mutated"]

    with pytest.raises(ValueError, match="canonical pressure proof"):
        write_schedule_file(target, publication)

    assert not target.exists()
    assert list(tmp_path.glob("schedule.yaml.tmp.*")) == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda publication: publication.document["pressure_matches"][0].pop("law_ids"),
            "missing typed proof fields",
        ),
        (
            lambda publication: publication.document["pressure_matches"][0].__setitem__("fact_ids", ["", "fact_food"]),
            "fact_ids must contain typed IDs",
        ),
        (
            lambda publication: publication.document["pressure_matches"][0]["provenance_refs"][0].__setitem__(
                "locator", None
            ),
            "provenance reference is malformed",
        ),
        (
            lambda publication: publication.document["domain_loads"]["daily"].__setitem__("squared_load", True),
            "domain squared load is malformed",
        ),
        (
            lambda publication: publication.document["canonical_explanations"]["item_demo"]["slot_anchors"].__setitem__(
                "meal_context", None
            ),
            "placement explanation is missing slot anchors",
        ),
    ],
)
def test_publication_revalidation_rejects_each_malformed_proof_section(mutate, message: str) -> None:
    publication = _publication()
    mutate(publication)

    with pytest.raises(ValueError, match=message):
        publication.validate()


def test_successful_publication_replaces_lease_with_complete_optimal_document(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("status: Optimal\nassignments: {stale: stale}\n", encoding="utf-8")

    write_schedule_file(target, _publication())

    rendered = target.read_text(encoding="utf-8")
    assert "status: Optimal" in rendered
    assert "satisfied_pressures: 1" in rendered
    assert "optimizer_proof:" in rendered
    assert "stale" not in rendered


@pytest.mark.parametrize(
    ("error", "code"),
    [(KeyboardInterrupt(), "interrupted"), (MemoryError(), "resource_exhausted")],
)
def test_public_plan_boundary_invalidates_stale_lease_before_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException, code: str
) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("status: Optimal\nassignments: {stale: stale}\n", encoding="utf-8")
    monkeypatch.setattr(plan_module, "load_ontology", lambda _path: object())

    def interrupt(*_args: object) -> object:
        raise error

    monkeypatch.setattr(plan_module, "_cmd_plan_inner", interrupt)

    result = plan_module.cmd_plan(data_root=tmp_path)

    assert result.status == "Indeterminate"
    assert result.diagnostic is not None
    assert result.diagnostic.code == code
    assert not target.exists()


def test_show_cannot_emit_a_stale_layout_after_plan_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("status: Optimal\nassignments: {stale: stale}\n", encoding="utf-8")

    def fail_ontology(_path: Path) -> object:
        raise OntologyInfrastructureError("simulated ontology failure")

    monkeypatch.setattr(plan_module, "load_ontology", fail_ontology)

    result = cmd_show(tmp_path)

    assert result.exit_code == 1
    assert result.output == ""
    assert not target.exists()
