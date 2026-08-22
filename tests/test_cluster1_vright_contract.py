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

import scripts.generate_migration_ledger as migration_ledger
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


def test_canonical_shadow_catalog_and_topology_are_closed(schema: dict[str, Any]) -> None:
    definitions = cast(dict[str, dict[str, Any]], schema["$defs"])
    catalog = definitions["CanonicalFactCatalog"]
    expected_collections = {
        "composition_roles": "CompositionRole",
        "evidence_sources": "EvidenceSource",
        "food_effects": "FoodEffect",
        "acute_alertness_effects": "AcuteAlertnessEffect",
        "acute_sleep_effects": "AcuteSleepEffect",
        "pre_exercise_performance_effects": "PreExercisePerformanceEffect",
        "post_exercise_recovery_effects": "PostExerciseRecoveryEffect",
    }
    assert set(catalog["properties"]) == set(expected_collections)
    assert catalog.get("required", []) == []
    for name, item_class in expected_collections.items():
        assert catalog["properties"][name] == {
            "items": {"$ref": f"#/$defs/{item_class}"},
            "type": ["array", "null"],
        }
    assert _errors(schema, "CanonicalFactCatalog", {}) == []

    slot = definitions["LogicalSlot"]
    assert {"meal_context", "circadian_anchor", "exercise_anchor"} == {
        name for name in slot["properties"] if name.endswith("_context") or name.endswith("_anchor")
    }
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
    ):
        assert _errors(schema, "CanonicalFactCatalog", {forbidden: "x"}), forbidden


def test_shadow_catalog_and_topology_are_not_manifest_or_scheduler_inputs() -> None:
    manifest = cast(dict[str, Any], yaml.safe_load((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    catalogs = cast(list[dict[str, Any]], manifest["catalogs"])
    assert {catalog["root_class"] for catalog in catalogs}.isdisjoint(
        {"CanonicalFactCatalog", "LogicalSlotTopology"}
    )
    assert {field for field in PlanInputs._fields if "catalog" in field or "topology" in field} == set()


def test_migration_ledger_is_deterministic_complete_in_shape_and_fail_closed(tmp_path: Path) -> None:
    first_path = tmp_path / "ledger-first.yaml"
    second_path = tmp_path / "ledger-second.yaml"
    assert migration_ledger.main(["--root", str(ROOT), "--output", str(first_path)]) == 0
    assert migration_ledger.main(["--root", str(ROOT), "--output", str(second_path)]) == 0
    assert first_path.read_bytes() == second_path.read_bytes()

    document = cast(dict[str, Any], yaml.safe_load(first_path.read_text(encoding="utf-8")))
    coverage = cast(dict[str, Any], document["coverage"])
    counts = cast(dict[str, int], coverage["final_disposition_counts"])
    assert sum(counts.values()) == coverage["atom_count"]
    assert coverage["pending_atom_count"] == 0
    assert coverage["migration_complete"] is False
    assert coverage["outstanding_sol_adjudication_count"] == 1786
    assert "before deletion" in coverage["migration_blocker"]

    allowed = {"data/relations.yaml", "ontology/policies.yaml", "ontology/runtime-policy.yaml"}
    allowed.add("ontology/scheduling-constraints.yaml")
    source_paths = {str(atom["source_path"]) for atom in document["atoms"]}
    assert all(path.startswith(("data/substances/", "data/products/")) or path in allowed for path in source_paths)
    assert not any(
        "schedule.yaml" in path or "ontology/generated" in path or path in {"data/stacks.yaml", "data/pillboxes.yaml"}
        for path in source_paths
    )

    authoritative = tmp_path / "authoritative"
    source = authoritative / "data/substances/source.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("id: sub_demo\n", encoding="utf-8")

    def fake_git(_root: Path, *args: str) -> str:
        if args[0] == "ls-files":
            return "data/substances/source.yaml\0"
        if args[0] == "status":
            return " M data/substances/source.yaml\n"
        raise AssertionError(args)

    original_git = migration_ledger._git
    try:
        migration_ledger._git = fake_git
        with pytest.raises(RuntimeError, match="dirty authoritative inputs"):
            migration_ledger._tracked_authoritative_files(authoritative)
    finally:
        migration_ledger._git = original_git

    rogue = authoritative / "data/substances/rogue.yaml"
    rogue.write_text("id: sub_rogue\n", encoding="utf-8")

    def fake_untracked_git(_root: Path, *args: str) -> str:
        if args[0] == "ls-files":
            return "data/substances/source.yaml\0"
        if args[0] == "status":
            return "?? data/substances/rogue.yaml\n"
        raise AssertionError(args)

    try:
        migration_ledger._git = fake_untracked_git
        with pytest.raises(RuntimeError, match="untracked authoritative inputs"):
            migration_ledger._tracked_authoritative_files(authoritative)
    finally:
        migration_ledger._git = original_git
