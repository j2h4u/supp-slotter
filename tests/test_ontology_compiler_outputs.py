"""Focused contract tests for the Wave B compiler output inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from planner.ontology.generate import compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
EXPECTED = {
    "card.schema.json",
    "schema.json",
    "ontology.ttl",
    "shapes.ttl",
    "context.json",
    "projection-map.json",
    "runtime-program.json",
    "runtime-vocabulary.yaml",
    "artifact-lock.json",
}


def _json(artifacts: dict[Path, bytes], name: str) -> dict[str, object]:
    return json.loads(artifacts[Path(name)])


def test_compilation_is_byte_identical_and_has_exact_inventory() -> None:
    first = compile_ontology(ONTOLOGY)
    second = compile_ontology(ONTOLOGY)
    assert first == second
    assert {path.name for path in first} == EXPECTED


def test_formats_and_lock_digests_are_valid() -> None:
    artifacts = compile_ontology(ONTOLOGY)
    for name in (
        "card.schema.json",
        "schema.json",
        "context.json",
        "projection-map.json",
        "runtime-program.json",
        "artifact-lock.json",
    ):
        json.loads(artifacts[Path(name)])
    yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")])

    lock = _json(artifacts, "artifact-lock.json")
    assert lock["format_version"] == "ontology-artifact-lock-v1"
    assert "timestamp" not in json.dumps(lock)
    assert all(not Path(str(item["path"])).is_absolute() for item in lock["sources"] + lock["outputs"])
    for item in lock["outputs"]:
        path = Path(str(item["path"]))
        assert hashlib.sha256(artifacts[path].__bytes__()).hexdigest() == item["sha256"]


def test_projection_matches_schema_and_runtime_program_is_domain_free() -> None:
    artifacts = compile_ontology(ONTOLOGY)
    schema = _json(artifacts, "schema.json")
    projection = _json(artifacts, "projection-map.json")
    assert set(schema["$defs"]) == {str(item["name"]) for item in projection["classes"]}

    runtime_program = _json(artifacts, "runtime-program.json")
    assert runtime_program["rules"] == []
    assert runtime_program["tables"] == []
    assert set(runtime_program) == {"format_version", "schema_version", "protocol", "rules", "tables"}
