"""Focused V-right checks for the closed canonical publication boundary."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from planner.contracts import MealContext, Product, ProductComponent, Slot
from planner.engine._canonical_optimizer import Indeterminate, Optimal, optimize_canonical_layout
from planner.engine._plan_output import CanonicalScheduleOutputInput, build_canonical_schedule_output
from planner.ontology.canonical_inference import Success, UnaryPressureIdentity
from planner.ontology.runtime_program import (
    RuntimeCanonicalFactCatalog,
    RuntimeCanonicalLaw,
    RuntimeCompositionRole,
    RuntimeEvidenceProvenance,
    RuntimeEvidenceSource,
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
        (),
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
        composition_roles=(role,),
        evidence_sources=(RuntimeEvidenceSource("src_demo"),),
        food_effects=(
            RuntimeFoodEffect(
                "fact_food",
                RuntimeFactSubject("sub_demo", None),
                role.id,
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

    result = execute_canonical_inference(catalog, {"item_demo": "prd_demo"}, (law,))
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
    product = Product("prd_demo", "Demo", (ProductComponent("sub_demo"),), use_pattern="not_every_day")
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
    groups = cast(dict[str, list[str]], summary["usage_groups"])
    pillboxes = cast(dict[str, dict[str, object]], document["pillboxes"])
    slots_out = cast(dict[str, dict[str, object]], pillboxes["daily"]["slots"])
    assert groups == {"daily_base": [], "not_every_day": ["Demo"]}
    assert slots_out["food"]["products"] == ["Demo"]
    assert slots_out["plain"]["products"] == []


def test_publication_boundary_refuses_indeterminate_and_legacy_documents(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    indeterminate = Indeterminate(("timeout",))
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
def test_atomic_write_failure_preserves_existing_document_and_cleans_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    target = tmp_path / "schedule.yaml"
    original = b"pre-existing schedule\n"
    target.write_bytes(original)

    def fail_fsync(_fd: int) -> None:
        raise error

    import planner.schedule_writer as schedule_writer

    monkeypatch.setattr(schedule_writer.os, "fsync", fail_fsync)
    with pytest.raises(type(error)):
        write_schedule_file(target, _publication())
    assert target.read_bytes() == original
    assert list(tmp_path.glob("schedule.yaml.tmp.*")) == []


def test_writer_revalidates_a_mutated_publication_before_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    original = b"pre-existing schedule\n"
    target.write_bytes(original)
    publication = _publication()
    publication.document["pressure_matches"][0]["law_ids"] = ["law_mutated"]

    with pytest.raises(ValueError, match="canonical pressure proof"):
        write_schedule_file(target, publication)

    assert target.read_bytes() == original
    assert list(tmp_path.glob("schedule.yaml.tmp.*")) == []
