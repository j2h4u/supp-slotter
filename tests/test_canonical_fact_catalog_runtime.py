"""Acceptance for the generic compiler-emitted scheduling fact projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.canonical_inference import Success, execute_canonical_inference
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_program import (
    RuntimeCanonicalSchedulingFact,
    RuntimeCompositionRole,
    decode_runtime_program,
)
from scripts.ontology_compiler import (
    _canonical_scheduling,
    _catalog_path,
    _load_yaml_mapping,
    _schema_view,
    compile_ontology,
)

from tests.test_ontology_artifacts import _copy_repository_shape

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(compile_ontology(ONTOLOGY)[Path("runtime-program.json")]))


def test_compiler_emits_one_generic_scheduling_projection_without_retired_catalog_keys() -> None:
    projection = cast(dict[str, object], _payload()["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])

    assert set(scheduling) == {"dimensions", "families", "evidence_sources", "facts", "laws"}
    assert "canonical_fact_catalog" not in projection
    assert all("effects" not in key for key in scheduling)
    assert len(cast(list[object], scheduling["facts"])) == 11


def test_decoder_types_facts_once_with_family_as_data() -> None:
    scheduling = decode_runtime_program(_payload()).canonical_scheduling

    assert all(isinstance(fact, RuntimeCanonicalSchedulingFact) for fact in scheduling.facts)
    assert {fact.family for fact in scheduling.facts} <= set(scheduling.families_by_id)
    assert {fact.value for fact in scheduling.facts} <= {
        value for family in scheduling.families for value in family.fact_values
    }


@pytest.mark.parametrize("mutation", ("unknown_family", "unadmitted_value", "duplicate_id"))
def test_decoder_rejects_malformed_generic_fact_rows(mutation: str) -> None:
    payload = _payload()
    projection = cast(dict[str, object], payload["projection"])
    scheduling = cast(dict[str, object], projection["canonical_scheduling"])
    facts = cast(list[dict[str, object]], scheduling["facts"])
    if mutation == "unknown_family":
        facts[0]["family"] = "Unknown"
    elif mutation == "unadmitted_value":
        facts[0]["value"] = "unknown"
    else:
        facts.append(dict(facts[0]))

    with pytest.raises(OntologyInfrastructureError):
        decode_runtime_program(payload)


def test_annotation_and_manifest_ranges_admit_a_new_family_without_python_changes(tmp_path: Path) -> None:  # noqa: PLR0914
    """An unrelated collection and a non-``Law`` rule class remain non-executable."""
    ontology = _copy_repository_shape(tmp_path)
    model_path = ontology / "model.yaml"
    scheduling_path = ontology / "scheduling-model.yaml"
    facts_path = ontology / "canonical-facts.yaml"
    laws_path = ontology / "canonical-laws.yaml"
    model = cast(dict[str, object], yaml.safe_load(model_path.read_text(encoding="utf-8")))
    scheduling = cast(dict[str, object], yaml.safe_load(scheduling_path.read_text(encoding="utf-8")))
    facts = cast(dict[str, object], yaml.safe_load(facts_path.read_text(encoding="utf-8")))
    laws = cast(dict[str, object], yaml.safe_load(laws_path.read_text(encoding="utf-8")))

    enums = cast(dict[str, object], model["enums"])
    enums["SyntheticAnchor"] = {
        "annotations": {"canonical_pressure_dimension": "synthetic_anchor"},
        "permissible_values": {"near_synthetic": None},
    }
    classes = cast(dict[str, object], model["classes"])
    slot_class = cast(dict[str, object], classes["Slot"])
    cast(list[object], slot_class["slots"]).append("synthetic_anchor")
    cast(dict[str, object], slot_class["slot_usage"])["synthetic_anchor"] = {
        "range": "SyntheticAnchor",
        "multivalued": False,
        "annotations": {"canonical_pressure_dimension": "synthetic_anchor"},
    }
    cast(dict[str, object], model["slots"])["synthetic_anchor"] = {"range": "SyntheticAnchor", "multivalued": False}

    scheduling_classes = cast(dict[str, object], scheduling["classes"])
    fact_root = cast(dict[str, object], scheduling_classes["CanonicalFactCatalog"])
    law_root = cast(dict[str, object], scheduling_classes["CanonicalLawCatalog"])
    cast(list[object], fact_root["slots"]).extend(("synthetic_observations", "unrelated_archive"))
    cast(dict[str, object], fact_root["slot_usage"]).update({
        "synthetic_observations": {
            "multivalued": True,
            "range": "SyntheticEffect",
            "inlined": True,
            "inlined_as_list": True,
        },
        "unrelated_archive": {
            "multivalued": True,
            "range": "IncidentalRecord",
            "inlined": True,
            "inlined_as_list": True,
        },
    })
    cast(list[object], law_root["slots"]).extend(("synthesis_table", "ignored_ledger"))
    cast(dict[str, object], law_root["slot_usage"]).update({
        "synthesis_table": {
            "multivalued": True,
            "range": "SyntheticInferenceRule",
            "inlined": True,
            "inlined_as_list": True,
        },
        "ignored_ledger": {"multivalued": True, "range": "IncidentalRecord", "inlined": True, "inlined_as_list": True},
    })
    scheduling_classes["SyntheticEffect"] = {
        "is_a": "CanonicalSchedulingFact",
        "slots": ["value"],
        "annotations": {"canonical_fact_family": "SyntheticEffect", "canonical_fact_value_slot": "value"},
        "slot_usage": {"value": {"required": True, "range": "SyntheticEffectValue", "multivalued": False}},
    }
    scheduling_classes["SyntheticInferenceRule"] = {
        "slots": ["id", "fact_value", "pressure_value"],
        "annotations": {
            "canonical_fact_family": "SyntheticEffect",
            "canonical_fact_value_slot": "fact_value",
            "canonical_pressure_dimension": "synthetic_anchor",
            "canonical_pressure_value_slot": "pressure_value",
        },
        "slot_usage": {
            "id": {"required": True},
            "fact_value": {"required": True, "range": "SyntheticEffectValue", "multivalued": False},
            "pressure_value": {"required": True, "range": "SyntheticAnchor", "multivalued": False},
        },
    }
    scheduling_classes["IncidentalRecord"] = {"slots": ["id"]}
    cast(dict[str, object], scheduling["enums"])["SyntheticEffectValue"] = {"permissible_values": {"helps": None}}
    cast(dict[str, object], scheduling["slots"]).update({
        "synthetic_observations": {
            "multivalued": True,
            "range": "SyntheticEffect",
            "inlined": True,
            "inlined_as_list": True,
        },
        "unrelated_archive": {
            "multivalued": True,
            "range": "IncidentalRecord",
            "inlined": True,
            "inlined_as_list": True,
        },
        "synthesis_table": {
            "multivalued": True,
            "range": "SyntheticInferenceRule",
            "inlined": True,
            "inlined_as_list": True,
        },
        "pressure_value": {"range": "SyntheticAnchor", "multivalued": False},
        "ignored_ledger": {"multivalued": True, "range": "IncidentalRecord", "inlined": True, "inlined_as_list": True},
    })
    source = cast(list[dict[str, object]], facts["evidence_sources"])[0]["id"]
    facts["synthetic_observations"] = [
        {
            "id": "fact_synthetic",
            "subject": {"substance": "sub_synthetic"},
            "applicability": {"substance": "sub_synthetic"},
            "provenance": [{"source": source, "locator": "synthetic#1"}],
            "value": "helps",
        }
    ]
    facts["unrelated_archive"] = [{"id": "incidental_fact"}]
    laws["synthesis_table"] = [{"id": "rule_synthetic", "fact_value": "helps", "pressure_value": "near_synthetic"}]
    laws["ignored_ledger"] = [{"id": "incidental_rule"}]
    for path, payload in ((model_path, model), (scheduling_path, scheduling), (facts_path, facts), (laws_path, laws)):
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    runtime_program = decode_runtime_program(
        cast(dict[str, object], json.loads(compile_ontology(ontology)[Path("runtime-program.json")]))
    )
    runtime = runtime_program.canonical_scheduling
    assert "SyntheticEffect" in runtime.families_by_id
    result = execute_canonical_inference(
        runtime,
        {"item_synthetic": "prd_synthetic"},
        applicability_expansion_strategy=runtime_program.engine_contract.applicability_expansion_strategy,
        composition_roles=(RuntimeCompositionRole("cmp_synthetic", "prd_synthetic", "sub_synthetic"),),
        known_products=("prd_synthetic",),
    )
    assert isinstance(result, Success)
    assert {(row.dimension, row.value) for row in result.pressures} >= {("synthetic_anchor", "near_synthetic")}


def test_runtime_boundary_has_no_descriptor_dsl_or_family_name_heuristics() -> None:
    compiler = (ROOT / "scripts/ontology_compiler.py").read_text(encoding="utf-8")
    protocol = (ONTOLOGY / "runtime-protocol.yaml").read_text(encoding="utf-8")
    plan_types = (ROOT / "planner/engine/_plan_types.py").read_text(encoding="utf-8")
    active_index = (ROOT / "planner/engine/_plan_active_index.py").read_text(encoding="utf-8")
    assert "runtime_projection" not in compiler
    assert "RuntimeProjectionDescriptor" not in protocol
    assert "canonical_catalog_slot" not in compiler
    assert 'endswith("Law")' not in compiler
    assert "canonical_scheduling:" not in plan_types
    assert "index_input.canonical_scheduling" not in active_index


@pytest.mark.parametrize("mutation", ("fact_annotation", "topology_dimension", "law_coverage"))
def test_annotation_range_topology_and_law_coverage_fail_closed(tmp_path: Path, mutation: str) -> None:
    ontology = _copy_repository_shape(tmp_path)
    manifest = _load_yaml_mapping(ontology / "manifest.yaml")
    model_path = ontology / "model.yaml"
    scheduling_path = ontology / "scheduling-model.yaml"
    facts_path = _catalog_path(ontology, manifest, "canonical_facts")
    laws_path = _catalog_path(ontology, manifest, "canonical_laws")
    if mutation == "fact_annotation":
        scheduling = cast(dict[str, object], yaml.safe_load(scheduling_path.read_text(encoding="utf-8")))
        annotations = cast(dict[str, object], cast(dict[str, object], scheduling["classes"])["FoodEffect"])[
            "annotations"
        ]
        cast(dict[str, object], annotations).pop("canonical_fact_value_slot")
        scheduling_path.write_text(yaml.safe_dump(scheduling, sort_keys=False), encoding="utf-8")
    elif mutation == "topology_dimension":
        model = cast(dict[str, object], yaml.safe_load(model_path.read_text(encoding="utf-8")))
        slot_usage = cast(dict[str, object], cast(dict[str, object], model["classes"])["Slot"])["slot_usage"]
        cast(dict[str, object], cast(dict[str, object], slot_usage)["meal_context"])["annotations"] = {}
        model_path.write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")
    else:
        laws = cast(dict[str, object], yaml.safe_load(laws_path.read_text(encoding="utf-8")))
        cast(list[object], laws["food_effect_laws"]).pop()
        laws_path.write_text(yaml.safe_dump(laws, sort_keys=False), encoding="utf-8")

    schema = _schema_view(ontology, manifest)
    facts = _load_yaml_mapping(facts_path)
    laws = _load_yaml_mapping(laws_path)
    with pytest.raises(OntologyInfrastructureError):
        _canonical_scheduling(schema, manifest, facts, laws)
