"""V-right acceptance for canonical law execution and pressure normalization."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from planner.ontology.canonical_inference import (
    Conflict,
    Success,
    UnaryPressureIdentity,
    execute_canonical_inference,
)
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    RuntimeAcuteAlertnessEffect,
    RuntimeAcuteSleepEffect,
    RuntimeCanonicalFactCatalog,
    RuntimeCanonicalLaw,
    RuntimeCompositionRole,
    RuntimeEvidenceProvenance,
    RuntimeEvidenceSource,
    RuntimeFactApplicability,
    RuntimeFactSubject,
    RuntimeFoodEffect,
    RuntimePostExerciseRecoveryEffect,
    RuntimePreExercisePerformanceEffect,
    decode_runtime_program,
)
from scripts.ontology_compiler import _normalize_canonical_laws, compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"

ROLE = RuntimeCompositionRole("cmp_prd_demo__sub_demo", "prd_demo", "sub_demo")
OTHER_ROLE = RuntimeCompositionRole("cmp_prd_other__sub_demo", "prd_other", "sub_demo")
SOURCE = RuntimeEvidenceSource("src_demo")
PROVENANCE = (RuntimeEvidenceProvenance("src_demo", "paper#demo", "quote"),)


def _laws() -> tuple[RuntimeCanonicalLaw, ...]:
    rows = (
        ("FoodEffect", "bioavailability_increases", "meal_context", "with_food"),
        ("FoodEffect", "bioavailability_decreases", "meal_context", "without_food"),
        ("FoodEffect", "tolerability_improves", "meal_context", "with_food"),
        ("FoodEffect", "tolerability_worsens", "meal_context", "without_food"),
        ("AcuteAlertnessEffect", "acute_alertness_increases", "circadian_anchor", "wake"),
        ("AcuteSleepEffect", "onset_latency_decreases", "circadian_anchor", "sleep"),
        ("AcuteSleepEffect", "continuity_improves", "circadian_anchor", "sleep"),
        ("PreExercisePerformanceEffect", "performance_improves", "exercise_anchor", "before"),
        ("PostExerciseRecoveryEffect", "recovery_improves", "exercise_anchor", "after"),
    )
    return tuple(RuntimeCanonicalLaw(f"law_{index}", *row) for index, row in enumerate(rows))


def _catalog(*facts: object) -> RuntimeCanonicalFactCatalog:
    families = {
        RuntimeFoodEffect: [],
        RuntimeAcuteAlertnessEffect: [],
        RuntimeAcuteSleepEffect: [],
        RuntimePreExercisePerformanceEffect: [],
        RuntimePostExerciseRecoveryEffect: [],
    }
    for fact in facts:
        for family in families:
            if isinstance(fact, family):
                families[family].append(fact)
                break
    return RuntimeCanonicalFactCatalog(
        evidence_sources=(SOURCE,),
        food_effects=tuple(families[RuntimeFoodEffect]),
        acute_alertness_effects=tuple(families[RuntimeAcuteAlertnessEffect]),
        acute_sleep_effects=tuple(families[RuntimeAcuteSleepEffect]),
        pre_exercise_performance_effects=tuple(families[RuntimePreExercisePerformanceEffect]),
        post_exercise_recovery_effects=tuple(families[RuntimePostExerciseRecoveryEffect]),
    )


def _fact(
    family: str,
    value: str,
    *,
    subject: RuntimeFactSubject | None = None,
    applicability: RuntimeFactApplicability | None = None,
    fact_id: str = "fact_demo",
) -> object:
    cls = {
        "FoodEffect": RuntimeFoodEffect,
        "AcuteAlertnessEffect": RuntimeAcuteAlertnessEffect,
        "AcuteSleepEffect": RuntimeAcuteSleepEffect,
        "PreExercisePerformanceEffect": RuntimePreExercisePerformanceEffect,
        "PostExerciseRecoveryEffect": RuntimePostExerciseRecoveryEffect,
    }[family]
    return cls(
        fact_id,
        subject or RuntimeFactSubject("sub_demo", None),
        applicability or RuntimeFactApplicability("sub_demo", None),
        PROVENANCE,
        value,
    )


def _execute(
    catalog: RuntimeCanonicalFactCatalog,
    selected_items: object,
    laws: tuple[RuntimeCanonicalLaw, ...] | None = None,
    *,
    roles: tuple[RuntimeCompositionRole, ...] = (ROLE,),
) -> Success | Conflict:
    return execute_canonical_inference(catalog, selected_items, laws or _laws(), composition_roles=roles)  # type: ignore[arg-type]


def test_every_admitted_value_maps_to_one_pressure() -> None:
    """Execute the authored/compiled law table and reject generated drift."""

    authored = cast(dict[str, object], yaml.safe_load((ONTOLOGY / "canonical-laws.yaml").read_text(encoding="utf-8")))
    authored_laws = _normalize_canonical_laws(authored)
    compiled_payload = cast(dict[str, Any], json.loads(compile_ontology(ONTOLOGY)[Path("runtime-program.json")]))
    generated_payload = cast(
        dict[str, Any], json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8"))
    )
    compiled_laws = cast(dict[str, Any], compiled_payload["projection"])["canonical_laws"]
    generated_laws = cast(dict[str, Any], generated_payload["projection"])["canonical_laws"]
    assert compiled_laws == list(authored_laws)
    assert generated_laws == list(authored_laws)

    runtime_laws = decode_runtime_program(generated_payload).canonical_laws
    assert len(runtime_laws) == len(authored_laws) == 9
    for law in runtime_laws:
        result = _execute(_catalog(_fact(law.family, law.fact_value)), ("prd_demo",), runtime_laws)
        assert isinstance(result, Success)
        assert result.pressures[0].identity == UnaryPressureIdentity("prd_demo", law.dimension, law.pressure_value)
        assert result.pressures[0].derivations[0].family == law.family
        assert result.pressures[0].derivations[0].fact.value == law.fact_value  # type: ignore[attr-defined]


def test_wrong_or_unselected_applicability_does_not_emit_pressure() -> None:
    fact = _fact("FoodEffect", "bioavailability_increases")
    wrong_subject = _fact(
        "FoodEffect",
        "bioavailability_increases",
        subject=RuntimeFactSubject("sub_other", None),
        fact_id="fact_wrong_subject",
    )
    result = _execute(_catalog(fact, wrong_subject), ("prd_other",), _laws())
    assert isinstance(result, Success)
    assert result.pressures == ()


def test_substance_applicability_reaches_each_exact_matching_role() -> None:
    role_scoped = _fact(
        "FoodEffect",
        "bioavailability_increases",
        subject=RuntimeFactSubject(None, ROLE.id),
        applicability=RuntimeFactApplicability(None, ROLE.id),
        fact_id="fact_role_scoped",
    )
    substance_subject = _fact(
        "FoodEffect",
        "bioavailability_increases",
        fact_id="fact_substance_subject",
    )

    result = _execute(
        _catalog(role_scoped, substance_subject),
        {"item_primary": ROLE.product, "item_other": OTHER_ROLE.product},
        _laws(),
        roles=(ROLE, OTHER_ROLE),
    )

    assert isinstance(result, Success)
    assert tuple(pressure.identity for pressure in result.pressures) == (
        UnaryPressureIdentity("item_other", "meal_context", "with_food"),
        UnaryPressureIdentity("item_primary", "meal_context", "with_food"),
    )
    by_item = {pressure.item_id: pressure for pressure in result.pressures}
    assert {derivation.fact.id for derivation in by_item["item_primary"].derivations} == {
        "fact_role_scoped",
        "fact_substance_subject",
    }
    assert {derivation.fact.id for derivation in by_item["item_other"].derivations} == {"fact_substance_subject"}


def test_proof_contains_law_fact_subject_path_and_provenance() -> None:
    fact = _fact("FoodEffect", "bioavailability_increases")
    result = _execute(_catalog(fact), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    proof = result.pressures[0].derivations[0]
    assert proof.law.id == "law_0"
    assert proof.fact.id == "fact_demo"
    assert proof.subject == fact.subject  # type: ignore[attr-defined]
    assert proof.path.applicability_role == ROLE.id
    assert (proof.path.target_kind, proof.path.target_id) == ("substance", "sub_demo")
    assert proof.path.product == ROLE.product
    assert proof.provenance == PROVENANCE


def test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure() -> None:
    duplicate = replace(
        _fact("FoodEffect", "bioavailability_increases"),
        id="fact_duplicate",  # type: ignore[call-arg]
        provenance=PROVENANCE + PROVENANCE,  # type: ignore[arg-type]
    )
    result = _execute(_catalog(_fact("FoodEffect", "bioavailability_increases"), duplicate), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    assert len(result.pressures) == 1
    assert len(result.pressures[0].derivations) == 2
    assert result.pressures[0].derivations[1].provenance == PROVENANCE


def test_same_dimension_values_are_layout_free_conflict() -> None:
    result = _execute(
        _catalog(
            _fact("FoodEffect", "bioavailability_increases"),
            _fact("FoodEffect", "bioavailability_decreases", fact_id="fact_other"),
        ),
        ("prd_demo",),
        _laws(),
    )
    assert isinstance(result, Conflict)
    assert result.conflicts[0].item_id == "prd_demo"
    assert result.conflicts[0].dimension == "meal_context"
    assert result.conflicts[0].values == ("with_food", "without_food")


def test_cross_dimension_pressures_coexist() -> None:
    result = _execute(
        _catalog(
            _fact("FoodEffect", "bioavailability_increases"),
            _fact("AcuteAlertnessEffect", "acute_alertness_increases", fact_id="fact_alert"),
        ),
        ("prd_demo",),
        _laws(),
    )
    assert isinstance(result, Success)
    assert {(pressure.dimension, pressure.value) for pressure in result.pressures} == {
        ("meal_context", "with_food"),
        ("circadian_anchor", "wake"),
    }


def test_admitted_fact_without_exact_law_fails_closed() -> None:
    laws = tuple(law for law in _laws() if law.fact_value != "bioavailability_increases")
    with pytest.raises(OntologyInfrastructureError, match="canonical law missing"):
        _execute(
            _catalog(_fact("FoodEffect", "bioavailability_increases")),
            ("prd_demo",),
            laws,
        )


def test_provenance_sort_is_deterministic_for_optional_quotations() -> None:
    provenance = (
        RuntimeEvidenceProvenance("src_demo", "paper#demo", "quoted"),
        RuntimeEvidenceProvenance("src_demo", "paper#demo", None),
        RuntimeEvidenceProvenance("src_demo", "paper#demo", "quoted"),
    )
    fact = replace(_fact("FoodEffect", "bioavailability_increases"), provenance=provenance)
    result = _execute(_catalog(fact), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    assert result.pressures[0].derivations[0].provenance == (provenance[1], provenance[0])
