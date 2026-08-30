"""Focused tests for the authoritative canonical-fact runtime projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import scripts.ontology_compiler as ontology_compiler
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    RuntimeAcuteAlertnessEffect,
    RuntimeAcuteSleepEffect,
    RuntimeCompositionRole,
    RuntimeFoodEffect,
    RuntimePostExerciseRecoveryEffect,
    RuntimePreExercisePerformanceEffect,
    decode_runtime_program,
)

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _runtime_payload() -> dict[str, object]:
    payload = cast(
        dict[str, object],
        json.loads((ONTOLOGY / "generated/runtime-program.json").read_text(encoding="utf-8")),
    )
    projection = cast(dict[str, object], payload["projection"])
    projection["canonical_fact_catalog"] = {
        "composition_roles": [],
        "evidence_sources": [],
        "food_effects": [],
        "acute_alertness_effects": [],
        "acute_sleep_effects": [],
        "pre_exercise_performance_effects": [],
        "post_exercise_recovery_effects": [],
    }
    return payload


def test_compiler_emits_authoritative_empty_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    # Product component identity migration is maintained by another wave.  A
    # compiler projection test should isolate canonical catalog emission from
    # that repository-wide projection gate.
    monkeypatch.setattr(ontology_compiler, "_validate_repository_projection_coverage", lambda *_args: None)
    artifacts = ontology_compiler.compile_ontology(ONTOLOGY)
    payload = cast(dict[str, object], json.loads(artifacts[Path("runtime-program.json")]))
    projection = cast(dict[str, object], payload["projection"])
    catalog = cast(dict[str, object], projection["canonical_fact_catalog"])
    assert set(catalog) == {
        "composition_roles",
        "evidence_sources",
        "food_effects",
        "acute_alertness_effects",
        "acute_sleep_effects",
        "pre_exercise_performance_effects",
        "post_exercise_recovery_effects",
    }
    assert all(value == [] for value in catalog.values())
    lock = cast(dict[str, object], json.loads(artifacts[Path("artifact-lock.json")]))
    sources = cast(list[dict[str, object]], lock["sources"])
    assert any(source["path"] == "ontology/canonical-facts.yaml" for source in sources)


def test_runtime_decodes_all_typed_fact_families() -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    projection["canonical_fact_catalog"] = {
        "composition_roles": [{"id": "cmp_demo", "product": "prd_demo", "substance": "sub_demo"}],
        "evidence_sources": [{"id": "src_demo"}],
        "food_effects": [
            {
                "id": "fact_food",
                "subject": {"substance": "sub_demo"},
                "applicability": "cmp_demo",
                "provenance": [{"source": "src_demo", "locator": "paper#food"}],
                "value": "bioavailability_increases",
            }
        ],
        "acute_alertness_effects": [
            {
                "id": "fact_alertness",
                "subject": {"composition_role": "cmp_demo"},
                "applicability": "cmp_demo",
                "provenance": [{"source": "src_demo", "locator": "paper#alertness", "quotation": "quoted"}],
                "value": "acute_alertness_increases",
            }
        ],
        "acute_sleep_effects": [
            {
                "id": "fact_sleep",
                "subject": {"composition_role": "cmp_demo"},
                "applicability": "cmp_demo",
                "provenance": [{"source": "src_demo", "locator": "paper#sleep"}],
                "value": "continuity_improves",
            }
        ],
        "pre_exercise_performance_effects": [
            {
                "id": "fact_pre",
                "subject": {"composition_role": "cmp_demo"},
                "applicability": "cmp_demo",
                "provenance": [{"source": "src_demo", "locator": "paper#pre"}],
                "value": "performance_improves",
            }
        ],
        "post_exercise_recovery_effects": [
            {
                "id": "fact_post",
                "subject": {"composition_role": "cmp_demo"},
                "applicability": "cmp_demo",
                "provenance": [{"source": "src_demo", "locator": "paper#post"}],
                "value": "recovery_improves",
            }
        ],
    }

    runtime = decode_runtime_program(payload)
    catalog = runtime.canonical_fact_catalog
    assert isinstance(catalog.composition_roles[0], RuntimeCompositionRole)
    assert isinstance(catalog.food_effects[0], RuntimeFoodEffect)
    assert isinstance(catalog.acute_alertness_effects[0], RuntimeAcuteAlertnessEffect)
    assert isinstance(catalog.acute_sleep_effects[0], RuntimeAcuteSleepEffect)
    assert isinstance(catalog.pre_exercise_performance_effects[0], RuntimePreExercisePerformanceEffect)
    assert isinstance(catalog.post_exercise_recovery_effects[0], RuntimePostExerciseRecoveryEffect)
    assert catalog.food_effects[0].subject.substance == "sub_demo"


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("duplicate", "duplicate fact IDs"),
        ("invalid_value", "not an admitted value"),
        ("both_subjects", "exactly one"),
        ("no_subject", "exactly one"),
        ("blank_locator", "must be a non-empty string"),
        ("whitespace_locator", "non-whitespace"),
    ],
)
def test_runtime_rejects_malformed_canonical_facts(mutation: str, match: str) -> None:
    payload = _runtime_payload()
    projection = cast(dict[str, object], payload["projection"])
    catalog = cast(dict[str, object], projection["canonical_fact_catalog"])
    fact = {
        "id": "fact_demo",
        "subject": {"composition_role": "cmp_demo"},
        "applicability": "cmp_demo",
        "provenance": [{"source": "src_demo", "locator": "paper#demo"}],
        "value": "bioavailability_increases",
    }
    catalog["food_effects"] = [fact]
    if mutation == "duplicate":
        catalog["acute_sleep_effects"] = [{**fact, "value": "continuity_improves"}]
    elif mutation == "invalid_value":
        fact["value"] = "not_admitted"
    elif mutation == "both_subjects":
        fact["subject"] = {"substance": "sub_demo", "composition_role": "cmp_demo"}
    elif mutation == "no_subject":
        fact["subject"] = {}
    elif mutation == "blank_locator":
        cast(list[dict[str, object]], fact["provenance"])[0]["locator"] = ""
    elif mutation == "whitespace_locator":
        cast(list[dict[str, object]], fact["provenance"])[0]["locator"] = "   "

    with pytest.raises(OntologyInfrastructureError, match=match):
        decode_runtime_program(payload)
