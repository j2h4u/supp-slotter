"""V-right acceptance for canonical law execution and pressure normalization."""

from __future__ import annotations

from dataclasses import replace

import pytest
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
    RuntimeFactSubject,
    RuntimeFoodEffect,
    RuntimePostExerciseRecoveryEffect,
    RuntimePreExercisePerformanceEffect,
)

ROLE = RuntimeCompositionRole("cmp_prd_demo__sub_demo", "prd_demo", "sub_demo")
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
        composition_roles=(ROLE,),
        evidence_sources=(SOURCE,),
        food_effects=tuple(families[RuntimeFoodEffect]),
        acute_alertness_effects=tuple(families[RuntimeAcuteAlertnessEffect]),
        acute_sleep_effects=tuple(families[RuntimeAcuteSleepEffect]),
        pre_exercise_performance_effects=tuple(families[RuntimePreExercisePerformanceEffect]),
        post_exercise_recovery_effects=tuple(families[RuntimePostExerciseRecoveryEffect]),
    )


def _fact(family: str, value: str, *, subject: RuntimeFactSubject | None = None, fact_id: str = "fact_demo") -> object:
    cls = {
        "FoodEffect": RuntimeFoodEffect,
        "AcuteAlertnessEffect": RuntimeAcuteAlertnessEffect,
        "AcuteSleepEffect": RuntimeAcuteSleepEffect,
        "PreExercisePerformanceEffect": RuntimePreExercisePerformanceEffect,
        "PostExerciseRecoveryEffect": RuntimePostExerciseRecoveryEffect,
    }[family]
    return cls(fact_id, subject or RuntimeFactSubject("sub_demo", None), ROLE.id, PROVENANCE, value)


@pytest.mark.parametrize(
    ("family", "value", "dimension", "pressure_value"),
    (
        ("FoodEffect", "bioavailability_increases", "meal_context", "with_food"),
        ("FoodEffect", "bioavailability_decreases", "meal_context", "without_food"),
        ("FoodEffect", "tolerability_improves", "meal_context", "with_food"),
        ("FoodEffect", "tolerability_worsens", "meal_context", "without_food"),
        ("AcuteAlertnessEffect", "acute_alertness_increases", "circadian_anchor", "wake"),
        ("AcuteSleepEffect", "onset_latency_decreases", "circadian_anchor", "sleep"),
        ("AcuteSleepEffect", "continuity_improves", "circadian_anchor", "sleep"),
        ("PreExercisePerformanceEffect", "performance_improves", "exercise_anchor", "before"),
        ("PostExerciseRecoveryEffect", "recovery_improves", "exercise_anchor", "after"),
    ),
)
def test_every_admitted_value_maps_to_one_pressure(
    family: str, value: str, dimension: str, pressure_value: str
) -> None:
    result = execute_canonical_inference(_catalog(_fact(family, value)), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    assert result.pressures[0].identity == UnaryPressureIdentity("prd_demo", dimension, pressure_value)
    assert result.pressures[0].derivations[0].family == family
    assert result.pressures[0].derivations[0].fact.value == value  # type: ignore[attr-defined]


def test_wrong_or_unselected_applicability_does_not_emit_pressure() -> None:
    fact = _fact("FoodEffect", "bioavailability_increases")
    wrong_subject = _fact(
        "FoodEffect",
        "bioavailability_increases",
        subject=RuntimeFactSubject("sub_other", None),
        fact_id="fact_wrong_subject",
    )
    result = execute_canonical_inference(_catalog(fact, wrong_subject), ("prd_other",), _laws())
    assert isinstance(result, Success)
    assert result.pressures == ()


def test_proof_contains_law_fact_subject_path_and_provenance() -> None:
    fact = _fact("FoodEffect", "bioavailability_increases")
    result = execute_canonical_inference(_catalog(fact), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    proof = result.pressures[0].derivations[0]
    assert proof.law.id == "law_0"
    assert proof.fact.id == "fact_demo"
    assert proof.subject == fact.subject  # type: ignore[attr-defined]
    assert proof.path.applicability_role == ROLE.id
    assert proof.path.product == ROLE.product
    assert proof.provenance == PROVENANCE


def test_duplicate_witnesses_facts_components_and_paths_normalize_to_one_pressure() -> None:
    duplicate = replace(
        _fact("FoodEffect", "bioavailability_increases"),
        id="fact_duplicate",  # type: ignore[call-arg]
        provenance=PROVENANCE + PROVENANCE,  # type: ignore[arg-type]
    )
    result = execute_canonical_inference(
        _catalog(_fact("FoodEffect", "bioavailability_increases"), duplicate), ("prd_demo",), _laws()
    )
    assert isinstance(result, Success)
    assert len(result.pressures) == 1
    assert len(result.pressures[0].derivations) == 2
    assert result.pressures[0].derivations[1].provenance == PROVENANCE


def test_same_dimension_values_are_layout_free_conflict() -> None:
    result = execute_canonical_inference(
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
    result = execute_canonical_inference(
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
        execute_canonical_inference(
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
    result = execute_canonical_inference(_catalog(fact), ("prd_demo",), _laws())
    assert isinstance(result, Success)
    assert result.pressures[0].derivations[0].provenance == (provenance[1], provenance[0])
