"""Wave B contract for the compiler-owned ontology artifact set.

These tests deliberately read the generated tree directly.  A missing or stale
artifact is an implementation failure, not a reason to skip the contract.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
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
JSON_ARTIFACTS = {
    "schema.json",
    "context.json",
    "projection-map.json",
    "runtime-program.json",
    "artifact-lock.json",
}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_LOCAL_ABSOLUTE = re.compile(r"(?:^|[\"'\s])/(?:home|tmp|opt|var|workspace|Users)/")
_WINDOWS_ABSOLUTE = re.compile(r"(?:^|[\"'\s])[A-Za-z]:[\\/]")
_METADATA_KEYS = re.compile(r"(?:timestamp|generated_at|created_at|updated_at)$", re.IGNORECASE)


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


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


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


def _authored_classes() -> set[str]:
    root = cast(dict[str, object], yaml.safe_load((ONTOLOGY / "supp_slotter.yaml").read_text(encoding="utf-8")))
    names = {"supp_slotter.yaml"}
    imports = root.get("imports", [])
    assert isinstance(imports, list)
    names.update(item + ".yaml" for item in imports if isinstance(item, str) and not item.startswith("linkml:"))
    classes: set[str] = set()
    for name in names:
        document = cast(dict[str, object], cast(object, yaml.safe_load((ONTOLOGY / name).read_text(encoding="utf-8"))))
        declared = document.get("classes", {})
        assert isinstance(declared, dict)
        classes.update(cast(str, key) for key in declared)
    return classes


def _walk(value: object) -> list[object]:
    values = [value]
    if isinstance(value, dict):
        for key, item in cast(dict[object, object], value).items():
            values.extend(_walk(key))
            values.extend(_walk(item))
    elif isinstance(value, list):
        for item in cast(list[object], value):
            values.extend(_walk(item))
    return values


def _assert_no_paths_or_timestamps() -> None:
    for path in sorted(GENERATED.iterdir()):
        assert path.is_file(), f"generated tree contains non-file entry: {path.name}"
        text = path.read_text(encoding="utf-8")
        assert not _LOCAL_ABSOLUTE.search(text), f"absolute local path leaked into {path.name}"
        assert not _WINDOWS_ABSOLUTE.search(text), f"absolute Windows path leaked into {path.name}"
        if path.suffix == ".json":
            values = _walk(_load_json(path.name))
        elif path.suffix in {".yaml", ".yml"}:
            values = _walk(cast(object, yaml.safe_load(text)))
        else:
            values = []
        for value in values:
            if isinstance(value, str):
                assert not _LOCAL_ABSOLUTE.search(value)
                assert not _WINDOWS_ABSOLUTE.search(value)
            if isinstance(value, str):
                assert not _METADATA_KEYS.search(value)
        if path.suffix in {".json", ".yaml", ".yml"}:
            parsed = _load_json(path.name) if path.suffix == ".json" else cast(object, yaml.safe_load(text))
            if isinstance(parsed, dict):
                assert not any(
                    _METADATA_KEYS.search(key) for key in _walk(cast(object, parsed)) if isinstance(key, str)
                )


def test_generated_inventory_is_exact_and_flat() -> None:
    actual = {path.name for path in GENERATED.iterdir() if path.is_file()}
    assert actual == ARTIFACTS
    assert all(path.parent == GENERATED for path in GENERATED.iterdir())


def test_json_outputs_are_strict_and_canonically_serialized() -> None:
    for name in JSON_ARTIFACTS:
        value = _load_json(name)
        assert (GENERATED / name).read_bytes() == _canonical_json(value)


def test_card_schema_has_stable_closed_card_shape() -> None:
    card = _load_json("card.schema.json")
    assert card["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert card["$id"] == f"{BASE_IRI}generated/card.schema.json"
    assert card["type"] == "object"
    assert card["required"] == ["id", "name"]
    properties = cast(dict[str, object], card["properties"])
    assert {"id", "name", "knowledge", "schedule", "schedule_governance"} <= set(properties)


def test_full_json_schema_contains_every_authored_root_class() -> None:
    schema = _load_json("schema.json")
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("$id") == f"{BASE_IRI}generated/schema.json"
    definitions = schema.get("$defs")
    assert isinstance(definitions, dict)
    assert _authored_classes() <= set(cast(dict[str, object], definitions))


def test_context_is_deterministic_json_ld_context() -> None:
    context_document = _load_json("context.json")
    context = context_document.get("@context")
    assert isinstance(context, dict)
    assert BASE_IRI in json.dumps(context, ensure_ascii=False)
    assert all(isinstance(key, str) and isinstance(value, (str, dict)) for key, value in context.items())


def test_projection_map_is_schema_only_and_manifest_catalogs_are_exact() -> None:
    projection = _load_json("projection-map.json")
    assert set(projection) == {"format_version", "schema_version", "schema_root", "classes", "catalogs"}
    assert projection["format_version"] == "ontology-projection-map-v1"
    assert projection["schema_version"] == _manifest()["schema_version"]
    assert projection["schema_root"] == f"{BASE_IRI}supp_slotter"
    classes = projection["classes"]
    assert isinstance(classes, list)
    class_records = cast(list[dict[str, object]], classes)
    assert class_records == sorted(class_records, key=lambda item: cast(str, item["name"]))
    for item in class_records:
        assert isinstance(item, dict)
        assert set(item) == {"name", "uri", "slots"}
        assert item["uri"] == f"{BASE_IRI}{item['name']}"
        slots = item["slots"]
        assert isinstance(slots, list)
        slot_records = cast(list[dict[str, object]], slots)
        assert slot_records == sorted(slot_records, key=lambda slot: cast(str, slot["name"]))
        for slot in slot_records:
            assert isinstance(slot, dict)
            assert set(slot) == {"name", "range", "multivalued", "required", "inlined", "inlined_as_list"}
            assert isinstance(slot["name"], str)
            assert slot["range"] is None or isinstance(slot["range"], str)
            assert all(isinstance(slot[key], bool) for key in ("multivalued", "required", "inlined", "inlined_as_list"))
    catalogs = projection["catalogs"]
    assert isinstance(catalogs, list)
    expected = [
        {key: catalog[key] for key in ("id", "role", "path", "root_class")}
        for catalog in cast(list[dict[str, object]], _manifest()["catalogs"])
    ]
    expected_catalogs = cast(list[dict[str, object]], expected)
    assert cast(list[dict[str, object]], catalogs) == sorted(expected_catalogs, key=lambda item: cast(str, item["id"]))


def test_runtime_program_is_generic_ir_without_migrated_rules() -> None:
    program = _load_json("runtime-program.json")
    assert set(program) == {"format_version", "schema_version", "protocol", "rules", "tables"}
    assert program["format_version"] == "ontology-runtime-program-v1"
    assert program["schema_version"] == _manifest()["schema_version"]
    protocol = program["protocol"]
    assert isinstance(protocol, dict)
    protocol_values = cast(dict[str, object], protocol)
    assert set(protocol_values) == {"condition_classes", "action_classes", "gate_classes"}
    for key in protocol_values:
        values = protocol_values[key]
        assert isinstance(values, list)
        strings = cast(list[str], values)
        assert strings == sorted(strings)
        assert all(isinstance(value, str) for value in strings)
    assert program["rules"] == []
    assert program["tables"] == []


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


def test_rdf_contains_schema_classes_and_manifest_catalog_resources() -> None:
    text = (GENERATED / "ontology.ttl").read_text(encoding="utf-8")
    assert BASE_IRI in text
    for name in _authored_classes():
        assert f"{BASE_IRI}{name}" in text or f"ss:{name}" in text
    for catalog in cast(list[dict[str, object]], _manifest()["catalogs"]):
        assert f"{BASE_IRI}catalog/{catalog['id']}" in text


def test_shapes_contain_generated_and_custom_shape_ids() -> None:
    text = (GENERATED / "shapes.ttl").read_text(encoding="utf-8")
    custom = (ONTOLOGY / "constraints/semantic.ttl").read_text(encoding="utf-8")
    shape_ids = cast(set[str], set(re.findall(r'sh:name\s+"([A-Za-z][A-Za-z0-9_-]*)"', custom)))
    assert shape_ids
    for shape_id in shape_ids:
        assert shape_id in text
    for class_name in _authored_classes():
        assert f"{class_name}Shape" in text


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


def test_json_artifacts_are_consumable_with_stdlib_only(tmp_path: Path) -> None:
    script = tmp_path / "consume_generated_json.py"
    script.write_text(
        """\
import importlib.abc
import json
import sys
from pathlib import Path


class ForbiddenImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if (
            fullname == "planner"
            or fullname.startswith("linkml")
            or fullname.startswith("scripts.ontology_compiler")
        ):
            raise ImportError(f"forbidden compiler import: {fullname}")
        return None


sys.meta_path.insert(0, ForbiddenImportGuard())
generated = Path(sys.argv[1])
names = (
    "card.schema.json",
    "schema.json",
    "context.json",
    "projection-map.json",
    "runtime-program.json",
    "artifact-lock.json",
)
for name in names:
    with (generated / name).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"{name} must contain a JSON object")

for forbidden in ("linkml", "scripts.ontology_compiler"):
    try:
        __import__(forbidden)
    except ImportError:
        pass
    else:
        raise AssertionError(f"import guard did not block {forbidden}")
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", str(script), str(GENERATED)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_generated_outputs_contain_no_timestamps_or_absolute_paths() -> None:
    _assert_no_paths_or_timestamps()
