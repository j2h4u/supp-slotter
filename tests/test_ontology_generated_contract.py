"""Wave B contract for the compiler-owned ontology artifact set.

These tests deliberately read the generated tree directly.  A missing or stale
artifact is an implementation failure, not a reason to skip the contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
GENERATED = ONTOLOGY / "generated"
BASE_IRI = "https://j2h4u.github.io/supp-slotter/ontology/v1/"
ARTIFACTS = {
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
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _manifest() -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))


def _load_json(name: str) -> dict[str, object]:
    path = GENERATED / name
    raw = path.read_text(encoding="utf-8")
    # card.schema.json predates the Wave B JSON outputs and carries a stable
    # generated provenance comment header.  Its payload remains strict JSON.
    if name == "card.schema.json":
        raw = "\n".join(line for line in raw.splitlines() if not line.startswith("#"))
    value = cast(object, json.loads(raw))
    assert isinstance(value, dict), f"{name} must contain a JSON object"
    return cast(dict[str, object], value)


def _manifest_source_paths() -> list[str]:
    manifest = _manifest()
    paths = {"ontology/manifest.yaml"}
    for key in (
        "linkml_root",
        "linkml_modules",
        "policy_sources",
        "constraint_sources",
        "assertion_sources",
        "custom_shapes",
    ):
        value = manifest.get(key)
        if isinstance(value, str):
            paths.add(value)
        elif isinstance(value, list):
            paths.update(cast(str, item) for item in value if isinstance(item, str))
    catalogs = manifest.get("catalogs", [])
    assert isinstance(catalogs, list)
    for catalog in catalogs:
        assert isinstance(catalog, dict)
        path = cast(dict[str, object], catalog).get("path")
        assert isinstance(path, str)
        paths.add(path)
    return sorted(paths)


def _assert_runtime_program_provenance(program: dict[str, object]) -> None:
    assert set(program) == {
        "format_version",
        "schema_version",
        "source_hash",
        "provenance",
        "protocol",
        "projection",
        "rules",
        "tables",
    }
    assert program["format_version"] == "ontology-runtime-program-v1"
    assert program["schema_version"] == _manifest()["schema_version"]
    assert isinstance(program["source_hash"], str) and _HEX64.fullmatch(cast(str, program["source_hash"]))
    provenance = cast(dict[str, object], program["provenance"])
    assert set(provenance) == {"source", "source_sha256", "manifest_schema_version", "compiler_sha256"}
    assert provenance["source"] == "ontology/runtime-policy.yaml"
    assert (
        provenance["source_sha256"] == hashlib.sha256((ROOT / cast(str, provenance["source"])).read_bytes()).hexdigest()
    )
    assert provenance["manifest_schema_version"] == _manifest()["schema_version"]
    assert isinstance(provenance["compiler_sha256"], str)
    assert _HEX64.fullmatch(cast(str, provenance["compiler_sha256"]))
    protocol = program["protocol"]
    assert isinstance(protocol, dict)
    protocol_values = cast(dict[str, object], protocol)
    assert set(protocol_values) == {"condition_classes", "action_classes", "gate_classes", "policy_class"}
    for key in protocol_values:
        if key == "policy_class":
            assert protocol_values[key] == "RuntimePolicyCatalog"
            continue
        values = protocol_values[key]
        assert isinstance(values, list)
        strings = cast(list[str], values)
        assert strings == sorted(strings)
        assert all(isinstance(value, str) for value in strings)
    rules = program["rules"]
    tables = program["tables"]
    projection = program["projection"]
    assert isinstance(projection, dict)
    assert isinstance(rules, list) and rules
    assert isinstance(tables, list) and tables


def test_runtime_program_is_provenance_bearing_and_semantically_nonempty() -> None:
    program = _load_json("runtime-program.json")
    _assert_runtime_program_provenance(program)

    source = cast(
        dict[str, object], yaml.safe_load((ROOT / "ontology/runtime-policy.yaml").read_text(encoding="utf-8"))
    )
    projection = cast(dict[str, object], program["projection"])
    execution_gates = cast(list[dict[str, object]], projection["execution_gates"])
    source_gates = cast(list[dict[str, object]], source["execution_gates"])
    assert {row["id"]: row for row in execution_gates} == {row["id"]: row for row in source_gates}
    capability = cast(list[dict[str, object]], projection["capability_rules"])[0]
    source_capability = cast(list[dict[str, object]], source["capability_rules"])[0]
    assert capability["near_to_model"] == source_capability["near_to_model"]
    scoring = cast(dict[str, object], projection["effect_scoring"])
    source_scoring = cast(dict[str, object], source["effect_scoring"])
    for key in ("prefer_with_bonus", "advisory_constraint_score_delta", "advisory_match_direction"):
        assert scoring[key] == source_scoring[key]
    governance = cast(dict[str, object], projection["constraint_governance"])
    source_governance = cast(dict[str, object], source["constraint_governance"])
    assert governance == source_governance


def test_runtime_loader_does_not_keep_generic_ir_or_condition_vocabulary_mirrors() -> None:
    source = "\n".join([
        (ROOT / "planner/ontology/runtime_program.py").read_text(encoding="utf-8"),
        (ROOT / "scripts/ontology_compiler.py").read_text(encoding="utf-8"),
    ])
    forbidden = (
        "_RULE_FIELDS",
        "_TABLE_FIELDS",
        "_RULE_FIELD_TYPES",
        "_TABLE_FIELD_TYPES",
        "_CONDITION_PATH_TYPES",
    )
    for marker in forbidden:
        assert marker not in source


def test_artifact_lock_digests_are_canonical_and_exclude_self() -> None:
    lock = _load_json("artifact-lock.json")
    assert set(lock) == {"format_version", "schema_version", "compiler", "sources", "outputs"}
    assert lock["format_version"] == "ontology-artifact-lock-v1"
    assert lock["schema_version"] == _manifest()["schema_version"]
    compiler = lock["compiler"]
    assert isinstance(compiler, dict)
    compiler_values = cast(dict[str, object], compiler)
    assert set(compiler_values) == {"identity", "version", "tools"}
    assert isinstance(compiler["identity"], str) and compiler["identity"]
    assert isinstance(compiler["version"], str) and compiler["version"]
    assert isinstance(compiler["tools"], dict)
    tools = cast(dict[str, object], compiler["tools"])
    assert all(isinstance(key, str) and isinstance(value, str) and value for key, value in tools.items())
    sources = lock["sources"]
    outputs = lock["outputs"]
    assert isinstance(sources, list) and isinstance(outputs, list)
    source_records = cast(list[dict[str, object]], sources)
    output_records = cast(list[dict[str, object]], outputs)
    assert source_records == sorted(source_records, key=lambda item: cast(str, item["path"]))
    assert output_records == sorted(output_records, key=lambda item: cast(str, item["path"]))
    assert [cast(str, item["path"]) for item in source_records] == _manifest_source_paths()
    assert [cast(str, item["path"]) for item in output_records] == sorted(ARTIFACTS - {"artifact-lock.json"})
    for item in [*source_records, *output_records]:
        assert isinstance(item, dict) and set(item) == {"path", "sha256"}
        assert isinstance(item["path"], str) and not Path(item["path"]).is_absolute()
        assert isinstance(item["sha256"], str) and _HEX64.fullmatch(item["sha256"])
    for item in source_records:
        assert item["sha256"] == hashlib.sha256((ROOT / cast(str, item["path"])).read_bytes()).hexdigest()
    for item in output_records:
        assert item["sha256"] == hashlib.sha256((GENERATED / cast(str, item["path"])).read_bytes()).hexdigest()


def test_runtime_vocabulary_is_compiler_derived_transitional_output() -> None:
    path = GENERATED / "runtime-vocabulary.yaml"
    runtime = cast(dict[str, object], cast(object, yaml.safe_load(path.read_text(encoding="utf-8"))))
    assert runtime["format"] == "supp-slotter.runtime-vocabulary/v2"
    assert runtime["schema_version"] == _manifest()["schema_version"]
    assert isinstance(runtime.get("source_hash"), str) and _HEX64.fullmatch(cast(str, runtime["source_hash"]))
    assert not (ONTOLOGY / "runtime-vocabulary.yaml").exists()
    authored = cast(
        dict[str, object], cast(object, yaml.safe_load((ONTOLOGY / "vocabulary.yaml").read_text(encoding="utf-8")))
    )
    terms = runtime.get("terms")
    source_terms = authored.get("terms")
    assert isinstance(terms, list) and isinstance(source_terms, list)
    runtime_terms = cast(list[dict[str, object]], terms)
    authored_terms = cast(list[dict[str, object]], source_terms)
    assert {(item["semantic_category"], item["slug"]) for item in runtime_terms} == {
        (item["semantic_category"], item["slug"]) for item in authored_terms
    }
