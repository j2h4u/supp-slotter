"""V-right acceptance checks for the closed universal law catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import decode_runtime_program
from scripts.ontology_compiler import _normalize_canonical_laws, compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


@pytest.fixture
def compiled() -> dict[Path, bytes]:
    return compile_ontology(ONTOLOGY)


@pytest.fixture
def schema(compiled: dict[Path, bytes]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(compiled[Path("schema.json")]))


def _errors(schema: dict[str, Any], class_name: str, instance: object) -> list[object]:
    validator = Draft202012Validator(schema)
    return list(validator.descend(instance, schema["$defs"][class_name]))


def _catalog() -> dict[str, object]:
    return cast(
        dict[str, object],
        yaml.safe_load((ONTOLOGY / "canonical-laws.yaml").read_text(encoding="utf-8")),
    )


def test_catalog_has_exactly_nine_typed_laws(schema: dict[str, Any], compiled: dict[Path, bytes]) -> None:
    catalog = _catalog()
    assert _errors(schema, "CanonicalLawCatalog", catalog) == []
    laws = _normalize_canonical_laws(catalog)
    assert len(laws) == 9
    assert {law["family"] for law in laws} == {
        "FoodEffect",
        "AcuteAlertnessEffect",
        "AcuteSleepEffect",
        "PreExercisePerformanceEffect",
        "PostExerciseRecoveryEffect",
    }
    assert all(set(law) == {"id", "family", "fact_value", "dimension", "pressure_value"} for law in laws)

    program = cast(dict[str, Any], json.loads(compiled[Path("runtime-program.json")]))
    projection = cast(dict[str, Any], program["projection"])
    assert projection["canonical_laws"] == list(laws)


def test_catalog_matches_complete_domain_truth_table() -> None:
    assert _normalize_canonical_laws(_catalog()) == (
        {
            "id": "law_food_bioavailability_increases",
            "family": "FoodEffect",
            "fact_value": "bioavailability_increases",
            "dimension": "meal_context",
            "pressure_value": "with_food",
        },
        {
            "id": "law_food_bioavailability_decreases",
            "family": "FoodEffect",
            "fact_value": "bioavailability_decreases",
            "dimension": "meal_context",
            "pressure_value": "without_food",
        },
        {
            "id": "law_food_tolerability_improves",
            "family": "FoodEffect",
            "fact_value": "tolerability_improves",
            "dimension": "meal_context",
            "pressure_value": "with_food",
        },
        {
            "id": "law_food_tolerability_worsens",
            "family": "FoodEffect",
            "fact_value": "tolerability_worsens",
            "dimension": "meal_context",
            "pressure_value": "without_food",
        },
        {
            "id": "law_acute_alertness_increases",
            "family": "AcuteAlertnessEffect",
            "fact_value": "acute_alertness_increases",
            "dimension": "circadian_anchor",
            "pressure_value": "wake",
        },
        {
            "id": "law_acute_sleep_onset_latency_decreases",
            "family": "AcuteSleepEffect",
            "fact_value": "onset_latency_decreases",
            "dimension": "circadian_anchor",
            "pressure_value": "sleep",
        },
        {
            "id": "law_acute_sleep_continuity_improves",
            "family": "AcuteSleepEffect",
            "fact_value": "continuity_improves",
            "dimension": "circadian_anchor",
            "pressure_value": "sleep",
        },
        {
            "id": "law_pre_exercise_performance_improves",
            "family": "PreExercisePerformanceEffect",
            "fact_value": "performance_improves",
            "dimension": "exercise_anchor",
            "pressure_value": "before",
        },
        {
            "id": "law_post_exercise_recovery_improves",
            "family": "PostExerciseRecoveryEffect",
            "fact_value": "recovery_improves",
            "dimension": "exercise_anchor",
            "pressure_value": "after",
        },
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "extra_collection", "duplicate", "wrong_value", "wrong_anchor", "wrong_family"]
)
def test_compiler_rejects_closed_catalog_mutations(mutation: str) -> None:
    catalog = _catalog()
    food = cast(list[dict[str, object]], catalog["food_effect_laws"])
    if mutation == "missing":
        food.pop()
    elif mutation == "extra":
        food.append(dict(food[0]))
    elif mutation == "extra_collection":
        catalog["unexpected_laws"] = []
    elif mutation == "duplicate":
        food[1]["id"] = food[0]["id"]
    elif mutation == "wrong_value":
        food[0]["fact_value"] = "performance_improves"
    elif mutation == "wrong_anchor":
        food[0]["meal_context"] = "wake"
    elif mutation == "wrong_family":
        food[0]["circadian_anchor"] = "wake"

    with pytest.raises(OntologyInfrastructureError):
        _normalize_canonical_laws(catalog)


def test_schema_rejects_extra_or_wrong_family_anchor(schema: dict[str, Any]) -> None:
    catalog = _catalog()
    row = cast(list[dict[str, object]], catalog["food_effect_laws"])[0]
    row["circadian_anchor"] = "wake"
    assert _errors(schema, "CanonicalLawCatalog", catalog)


@pytest.mark.parametrize("mutation", ["missing", "incomplete", "alias", "unmapped"])
def test_runtime_decoder_rejects_incomplete_or_unmapped_laws(compiled: dict[Path, bytes], mutation: str) -> None:
    payload = cast(dict[str, Any], json.loads(compiled[Path("runtime-program.json")]))
    projection = cast(dict[str, Any], payload["projection"])
    laws = cast(list[dict[str, Any]], projection["canonical_laws"])
    if mutation == "missing":
        del projection["canonical_laws"]
    elif mutation == "incomplete":
        laws.pop()
    elif mutation == "alias":
        laws[0]["value"] = laws[0].pop("pressure_value")
    elif mutation == "unmapped":
        laws[0]["fact_value"] = "not_an_admitted_fact_value"

    with pytest.raises(OntologyInfrastructureError):
        decode_runtime_program(payload)
