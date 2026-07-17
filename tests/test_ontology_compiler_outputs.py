"""Focused contract tests for the Wave B compiler output inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypeGuard, cast

import yaml
from scripts.ontology_compiler import compile_ontology

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


type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonMapping = dict[str, JsonValue]


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        items = cast(list[object], value)
        return all(_is_json_value(item) for item in items)
    if isinstance(value, dict):
        items = cast(dict[object, object], value)
        return all(isinstance(key, str) and _is_json_value(item) for key, item in items.items())
    return False


def _is_json_mapping(value: object) -> TypeGuard[JsonMapping]:
    return isinstance(value, dict) and _is_json_value(cast(object, value))


def _is_json_list(value: object) -> TypeGuard[list[JsonValue]]:
    return isinstance(value, list) and _is_json_value(cast(object, value))


def _json_mapping(value: object) -> JsonMapping:
    assert _is_json_mapping(value), "expected a JSON object"
    return value


def _json_mapping_list(value: object) -> list[JsonMapping]:
    assert _is_json_list(value) and all(_is_json_mapping(item) for item in value), "expected a JSON object list"
    return cast(list[JsonMapping], value)


def _json_string(value: object) -> str:
    assert isinstance(value, str), "expected a JSON string"
    return value


def _loaded_json(source: bytes) -> object:
    return cast(object, json.loads(source))


def _json(artifacts: dict[Path, bytes], name: str) -> JsonMapping:
    return _json_mapping(_loaded_json(artifacts[Path(name)]))


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
        _json_mapping(_loaded_json(artifacts[Path(name)]))
    assert _is_json_value(cast(object, yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")]))), "invalid YAML"

    lock = _json(artifacts, "artifact-lock.json")
    assert lock["format_version"] == "ontology-artifact-lock-v1"
    assert "timestamp" not in json.dumps(lock)
    lock_entries = _json_mapping_list(lock["sources"]) + _json_mapping_list(lock["outputs"])
    assert all(not Path(_json_string(item["path"])).is_absolute() for item in lock_entries)
    for item in _json_mapping_list(lock["outputs"]):
        path = Path(_json_string(item["path"]))
        assert hashlib.sha256(artifacts[path]).hexdigest() == _json_string(item["sha256"])


def test_projection_matches_schema_and_runtime_program_is_domain_free() -> None:
    artifacts = compile_ontology(ONTOLOGY)
    schema = _json(artifacts, "schema.json")
    projection = _json(artifacts, "projection-map.json")
    assert set(_json_mapping(schema["$defs"])) == {
        _json_string(item["name"]) for item in _json_mapping_list(projection["classes"])
    }

    runtime_program = _json(artifacts, "runtime-program.json")
    assert runtime_program["rules"] == []
    assert runtime_program["tables"] == []
    assert set(runtime_program) == {"format_version", "schema_version", "protocol", "rules", "tables"}
