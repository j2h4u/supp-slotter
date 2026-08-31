"""Compact V-right acceptance checks for the canonical-facts migration.

These tests compile the authored schema in memory.  They intentionally do not
rewrite committed generated artifacts or assert a full ledger snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator
from planner.engine._plan_types import PlanInputs
from scripts.ontology_compiler import compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    artifacts = compile_ontology(ONTOLOGY)
    return cast(dict[str, Any], json.loads(artifacts[Path("schema.json")]))


def _errors(schema: dict[str, Any], class_name: str, instance: object) -> list[object]:
    validator = Draft202012Validator(schema)
    return list(validator.descend(instance, schema["$defs"][class_name]))


@pytest.mark.parametrize(
    ("instance", "valid"),
    [
        ({"substance": "sub_demo"}, True),
        ({"composition_role": "cmp_demo"}, True),
        ({}, False),
        ({"substance": "sub_demo", "composition_role": "cmp_demo"}, False),
        ({"substance": None}, False),
        ({"composition_role": None}, False),
    ],
)
def test_fact_subject_is_exactly_one_non_null_typed_role(
    schema: dict[str, Any], instance: dict[str, object], valid: bool
) -> None:
    assert (_errors(schema, "FactSubject", instance) == []) is valid


def test_generic_exactly_one_repair_preserves_unrelated_nullability_and_arrays(
    schema: dict[str, Any],
) -> None:
    definitions = cast(dict[str, dict[str, Any]], schema["$defs"])

    # Optional scalar nullability is not part of an exactly-one branch.
    assert definitions["LogicalSlot"]["properties"]["label"]["type"] == ["string", "null"]
    # A required multivalued field remains an array and keeps its cardinality.
    components = definitions["ProductCard"]["properties"]["components"]
    assert components["type"] == "array"
    assert components["minItems"] == 1


@pytest.mark.parametrize(
    ("instance", "valid"),
    [
        ({"entity": {"entity_id": "sub_demo"}}, True),
        ({"category": "effect", "term": "marker"}, True),
        ({}, False),
        ({"entity": {"entity_id": "sub_demo"}, "category": "effect", "term": "marker"}, False),
        ({"category": "effect"}, False),
        ({"entity": {"entity_id": None}}, False),
    ],
)
def test_existing_relation_selector_positive_and_negative_contract(
    schema: dict[str, Any], instance: dict[str, object], valid: bool
) -> None:
    assert (_errors(schema, "RelationAssertionSelector", instance) == []) is valid


def test_canonical_catalog_and_topology_are_closed(schema: dict[str, Any]) -> None:
    definitions = cast(dict[str, dict[str, Any]], schema["$defs"])
    catalog = definitions["CanonicalFactCatalog"]
    collections = cast(dict[str, dict[str, Any]], catalog["properties"])
    assert "evidence_sources" in collections
    assert len(collections) > 1
    assert catalog.get("required", []) == []
    for collection in collections.values():
        assert collection["type"] == ["array", "null"]
        assert collection["items"]["$ref"].startswith("#/$defs/")
    assert _errors(schema, "CanonicalFactCatalog", {}) == []

    slot = definitions["LogicalSlot"]
    anchor_fields = {name for name in slot["properties"] if name.endswith(("_context", "_anchor"))}
    assert anchor_fields
    assert not {"near", "food", "capacity", "dose", "placement"} & set(slot["properties"])
    topology = definitions["LogicalSlotTopology"]
    assert set(topology["properties"]) == {"id", "label", "slots"}

    for forbidden in (
        "family",
        "predicate",
        "arbitrary_value",
        "dose",
        "frequency",
        "disease",
        "prose",
        "capacity",
        "placement",
        "desired_slot",
        "composition_roles",
    ):
        assert _errors(schema, "CanonicalFactCatalog", {forbidden: "x"}), forbidden

    law_catalog = definitions["CanonicalLawCatalog"]
    laws = cast(dict[str, dict[str, Any]], law_catalog["properties"])
    assert laws
    for law_collection in laws.values():
        law_class = law_collection["items"]["$ref"].removeprefix("#/$defs/")
        properties = definitions[law_class]["properties"]
        dimension_fields = set(properties) & anchor_fields
        assert set(properties) == {"id", "fact_value", *dimension_fields}
        assert len(dimension_fields) == 1
    assert _errors(schema, "CanonicalLawCatalog", {})


def test_runtime_program_is_the_only_plan_input_ontology_authority() -> None:
    manifest = cast(dict[str, Any], yaml.safe_load((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    catalogs = cast(list[dict[str, Any]], manifest["catalogs"])
    assert {catalog["root_class"] for catalog in catalogs}.isdisjoint({"LogicalSlotTopology"})
    assert "CanonicalLawCatalog" in {catalog["root_class"] for catalog in catalogs}
    # Scheduling and topology are reached through the one runtime program;
    # PlanInputs must not offer a second, injectable ontology authority.
    assert PlanInputs._fields.count("runtime_program") == 1
    assert not {field for field in PlanInputs._fields if "scheduling" in field or "topology" in field}
