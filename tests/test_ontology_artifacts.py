"""v2 ontology artifact and fail-closed generator contract."""

import os
import shutil
from pathlib import Path
from typing import TypeGuard, cast

import pytest
import yaml
from planner.ontology.artifacts import load_runtime_vocabulary
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_contract import runtime_assertions, validate_runtime_assertions
from scripts import ontology_compiler as generate_module
from scripts.ontology_compiler import generate_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"

type YamlScalar = None | bool | int | float | str
type YamlValue = YamlScalar | list[YamlValue] | dict[str, YamlValue]
type YamlMapping = dict[str, YamlValue]


def _is_yaml_value(value: object) -> TypeGuard[YamlValue]:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        items = cast(list[object], value)
        return all(_is_yaml_value(item) for item in items)
    if isinstance(value, dict):
        items = cast(dict[object, object], value)
        return all(isinstance(key, str) and _is_yaml_value(item) for key, item in items.items())
    return False


def _is_yaml_mapping(value: object) -> TypeGuard[YamlMapping]:
    return isinstance(value, dict) and _is_yaml_value(cast(object, value))


def _is_yaml_list(value: object) -> TypeGuard[list[YamlValue]]:
    return isinstance(value, list) and _is_yaml_value(cast(object, value))


def _yaml_mapping(value: object) -> YamlMapping:
    assert _is_yaml_mapping(value), "expected a YAML mapping"
    return value


def _object_mapping(value: object) -> dict[str, object]:
    """Return a mutable object mapping after validating its YAML value shape."""
    return cast(dict[str, object], _yaml_mapping(value))


def _object_list(value: object) -> list[object]:
    assert _is_yaml_list(value), "expected a YAML list"
    return cast(list[object], value)


def _string(value: object) -> str:
    assert isinstance(value, str), "expected a YAML string"
    return value


def _string_list(value: object) -> list[str]:
    assert _is_yaml_list(value) and all(isinstance(item, str) for item in value), "expected a YAML string list"
    return cast(list[str], value)


def _mapping_list(value: object) -> list[dict[str, object]]:
    assert _is_yaml_list(value) and all(_is_yaml_mapping(item) for item in value), "expected a YAML mapping list"
    return cast(list[dict[str, object]], value)


def _loaded_yaml(source: str | bytes) -> object:
    return cast(object, yaml.safe_load(source))


def _copy_repository_shape(tmp_path: Path) -> Path:  # noqa: C901, PLR0912
    """Create a repository-shaped fixture matching manifest repo-relative paths."""
    repository = tmp_path / "repo"
    copied_ontology = repository / "ontology"
    shutil.copytree(ONTOLOGY, copied_ontology)
    manifest = _object_mapping(_loaded_yaml((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    fields = (
        "linkml_root",
        "linkml_modules",
        "policy_sources",
        "constraint_sources",
        "assertion_sources",
        "custom_shapes",
    )
    paths: set[str] = set()
    for field in fields:
        value = manifest.get(field)
        if isinstance(value, str):
            paths.add(value)
        elif isinstance(value, list):
            paths.update(item for item in value if isinstance(item, str))
    catalogs = manifest.get("catalogs", [])
    if isinstance(catalogs, list):
        for catalog in _mapping_list(cast(object, catalogs)):
            path = catalog.get("path")
            if isinstance(path, str):
                paths.add(path)
    projection = manifest.get("repository_projection")
    if isinstance(projection, dict):
        for source in cast(list[object], cast(dict[str, object], projection).get("sources", [])):
            if not isinstance(source, dict):
                continue
            locator = cast(dict[str, object], source).get("locator")
            if not isinstance(locator, dict):
                continue
            locator = cast(dict[str, object], locator)
            kind = locator.get("kind")
            if kind == "catalog_ref":
                continue
            if kind == "flat_root":
                value = locator.get("path")
                if isinstance(value, str):
                    source_dir = ROOT / value
                    paths.update(
                        (Path(value) / child.name).as_posix()
                        for child in source_dir.iterdir()
                        if child.is_file() and child.suffix == ".yaml"
                    )
            elif kind == "explicit_path":
                value = locator.get("path")
                if isinstance(value, str):
                    paths.add(value)
            elif kind == "explicit_paths":
                values = locator.get("paths")
                if isinstance(values, list):
                    paths.update(item for item in values if isinstance(item, str))
    for relative in paths:
        source = ROOT / relative
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return copied_ontology


def test_runtime_v2_shape_and_catalog() -> None:
    runtime = load_runtime_vocabulary(ONTOLOGY)
    assert runtime["format"] == "supp-slotter.runtime-vocabulary/v2"
    assert runtime["schema_version"] == "2"
    assert isinstance(runtime["slot_policy_evidence"], dict)
    assert isinstance(runtime["scheduling_policies"], dict)
    assert isinstance(runtime["audit_review_rules"], list)
    assert runtime["assertions"] == runtime_assertions()
    assert isinstance(runtime["ontology_assertions"], dict)


def test_runtime_loader_reads_committed_projection_without_compiling(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest_path.write_text("not: the compiler input\n", encoding="utf-8")
    generated_before = (copied / "generated/runtime-vocabulary.yaml").read_bytes()

    runtime = load_runtime_vocabulary(copied)

    assert runtime["format"] == "supp-slotter.runtime-vocabulary/v2"
    assert (copied / "generated/runtime-vocabulary.yaml").read_bytes() == generated_before


def _mutated_assertions(case: str) -> object:
    assertions = runtime_assertions()
    if case == "missing":
        return None
    if case == "extra":
        assertions["extra"] = True
    elif case == "disabled":
        assertions["assignment_governance_required"] = False
    elif case == "reversed":
        assertions["scope_allowlist"] = list(reversed(_string_list(assertions["scope_allowlist"])))
    elif case == "diagnosis":
        values = _string_list(assertions["scope_allowlist"])
        values[values.index("formulation")] = "diagnosis"
    return assertions


@pytest.mark.parametrize("case", ["missing", "extra", "disabled", "reversed", "diagnosis"])
def test_runtime_assertions_validator_rejects_noncanonical_projection(case: str) -> None:
    validate_runtime_assertions(runtime_assertions())
    with pytest.raises(OntologyInfrastructureError):
        validate_runtime_assertions(_mutated_assertions(case))


@pytest.mark.parametrize("case", ["missing", "extra", "disabled", "reversed", "diagnosis"])
def test_runtime_v2_assertions_mutations_fail_closed(tmp_path: Path, case: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    runtime_path = copied / "generated/runtime-vocabulary.yaml"
    runtime = _object_mapping(_loaded_yaml(runtime_path.read_text(encoding="utf-8")))
    mutated = _mutated_assertions(case)
    if mutated is None:
        runtime.pop("assertions")
    else:
        runtime["assertions"] = mutated
    runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError):
        load_runtime_vocabulary(copied)


def test_generation_is_deterministic_and_fresh(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    generate_ontology(copied)
    first = {p.name: p.read_bytes() for p in (copied / "generated").iterdir()}
    generate_ontology(copied)
    assert {p.name: p.read_bytes() for p in (copied / "generated").iterdir()} == first
    generate_ontology(copied, check=True)


def test_v1_runtime_is_rejected_with_regeneration_guidance(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    runtime = copied / "generated/runtime-vocabulary.yaml"
    raw = _object_mapping(_loaded_yaml(runtime.read_text(encoding="utf-8")))
    raw["format"] = "supp-slotter.runtime-vocabulary/v1"
    runtime.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        load_runtime_vocabulary(copied)


@pytest.mark.parametrize("field", ["status", "enforcement", "scope", "evidence", "owner", "review_by"])
def test_missing_policy_governance_fails_closed(tmp_path: Path, field: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    policy_path = copied / "policies.yaml"
    authored = _object_mapping(_loaded_yaml(policy_path.read_text(encoding="utf-8")))
    policy = _object_mapping(_object_mapping(authored["scheduling_policies"])["intake:food_preferred"])
    policy.pop(field, None)
    policy_path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_ontology(copied)


def test_invalid_pending_block_and_retired_effects_fail(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    path = copied / "policies.yaml"
    authored = _object_mapping(_loaded_yaml(path.read_text(encoding="utf-8")))
    policies = _object_mapping(authored["scheduling_policies"])
    pending = _object_mapping(policies["activity:post_workout"])
    pending["enforcement"] = "block"
    path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_ontology(copied)


def test_evidence_catalog_rejects_empty_authoritative_text(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    path = copied / "policies.yaml"
    authored = _object_mapping(_loaded_yaml(path.read_text(encoding="utf-8")))
    catalog = _object_mapping(authored["slot_policy_evidence"])
    evidence = _object_mapping(catalog["enzyme.E5"])
    evidence["supports"] = ""
    path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="supports"):
        generate_ontology(copied)


def test_governance_normalization_helpers_preserve_contract() -> None:
    catalog = {"src": {"kind": "operational_contract"}}
    raw: dict[str, object] = {
        "status": "approved",
        "enforcement": "none",
        "scope": {"planner": "audit"},
        "evidence": [{"source": "src", "supports": "claim", "limitations": "limit"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    result = generate_module._normalize_record_governance("fixture", _object_mapping(raw), catalog, effects=[])
    assert result["status"] == "approved"
    assert result["scope"] == {"planner": "audit"}
    assert result["evidence"] == raw["evidence"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("scope", {}, "invalid scope"),
        ("evidence", "bad", "evidence must be a list"),
        ("review_by", "2026", "review_by must be YYYY-MM-DD"),
        ("enforcement", "block", "enforcement does not match effects"),
    ],
)
def test_governance_normalization_rejects_invalid_fields(field: str, value: object, message: str) -> None:
    raw: dict[str, object] = {
        "status": "approved",
        "enforcement": "none",
        "scope": {"planner": "audit"},
        "evidence": [{"source": "src", "supports": "claim", "limitations": "limit"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    raw[field] = value
    with pytest.raises(OntologyInfrastructureError, match=message):
        generate_module._normalize_record_governance("fixture", _object_mapping(raw), {"src": {}}, effects=[])


def test_governance_lifecycle_rejects_pending_block_and_retired_effects() -> None:
    base: dict[str, object] = {
        "status": "review_pending",
        "enforcement": "block",
        "scope": {"planner": "audit"},
        "evidence": [],
        "evidence_gap": "needs review",
        "owner": "team",
        "review_by": "2026-12-31",
    }
    with pytest.raises(OntologyInfrastructureError, match="cannot block"):
        generate_module._normalize_record_governance("fixture", _object_mapping(base), {}, effects=[])
    retired: dict[str, object] = {**base, "status": "retired", "enforcement": "none"}
    with pytest.raises(OntologyInfrastructureError, match="retired records"):
        generate_module._normalize_record_governance("fixture", _object_mapping(retired), {}, effects=[{"block": True}])


def test_audit_subject_shapes_and_evidence_validation() -> None:
    catalog: dict[str, object] = {"src": {}}
    assert generate_module._normalize_audit_subject("audit_x", {"disposition": "governed_assignment"}, catalog)
    reviewed: dict[str, object] = {
        "disposition": "reviewed_no_assignment",
        "status": "review_pending",
        "scope": {"planner": "audit"},
        "evidence": [],
        "evidence_gap": "pending",
        "owner": "team",
        "review_by": "2026-12-31",
    }
    assert (
        generate_module._normalize_audit_subject("audit_x", _object_mapping(reviewed), catalog)["status"]
        == "review_pending"
    )
    evidence_cases: list[list[object]] = [
        ["bad"],
        [{"source": "missing", "supports": "x", "limitations": "y"}],
        [{"source": "src"}],
    ]
    for evidence in evidence_cases:
        with pytest.raises(OntologyInfrastructureError):
            generate_module._validate_evidence_entries("fixture", _object_list(evidence), catalog)

    invalid: list[dict[str, object]] = [
        {"disposition": "governed_assignment", "extra": True},
        {"disposition": "wrong"},
        {"disposition": "reviewed_no_assignment", "status": "approved", "scope": {}, "evidence": []},
        {**reviewed, "evidence": "bad"},
        {**reviewed, "status": "approved", "evidence": []},
        {**reviewed, "evidence": [{"source": "src", "supports": "x", "limitations": "y"}], "owner": ""},
        {**reviewed, "evidence": [{"source": "src", "supports": "x", "limitations": "y"}], "review_by": "bad"},
    ]
    for item in invalid:
        with pytest.raises(OntologyInfrastructureError):
            generate_module._normalize_audit_subject("audit_x", _object_mapping(item), catalog)


def test_scheduling_constraint_normalizes_optional_fields() -> None:
    raw: dict[str, object] = {
        "legacy_relation_id": "rel_fixture",
        "assertion_type": "clinical_scheduling_constraint",
        "effect": "separate_slots",
        "enforcement": "advisory",
        "legacy_preserved": True,
        "status": "approved",
        "owner": "team",
        "review_by": "2026-12-31",
        "evidence": ["https://example.test/source"],
        "scope": {"planner": "fixture"},
        "source_selector": {"entity": {"id": "sub_a"}},
        "target_selector": {"entity": {"name": "Fixture"}},
        "rationale": "fixture rationale",
        "semantic_note": "fixture note",
        "action": "fixture action",
    }
    normalized = generate_module._normalize_scheduling_constraint("sc_fixture", _object_mapping(raw), set())
    assert normalized["semantic_note"] == "fixture note"
    assert normalized["action"] == "fixture action"
    for key, value in {
        "assertion_type": "wrong",
        "effect": "wrong",
        "enforcement": "none",
        "semantic_note": "",
        "action": "",
    }.items():
        invalid: dict[str, object] = {**raw, key: value}
        with pytest.raises(OntologyInfrastructureError):
            generate_module._normalize_scheduling_constraint("sc_fixture", _object_mapping(invalid), set())


def test_audit_review_rule_loader_rejects_invalid_shapes(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    ontology_root = repository / "ontology"
    ontology_root.mkdir(parents=True)
    policy_file = ontology_root / "policies.yaml"
    rule = {
        "priority": 1,
        "axis": "intake",
        "predicate": "reviewed_disposition_present",
        "subjects": {},
        "message": "fixture",
        "action": "fixture",
        "status": "retired",
        "enforcement": "none",
        "scope": {"planner": "audit"},
        "evidence": [{"source": "src", "supports": "x", "limitations": "y"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    cases = {
        "axis": {**rule, "axis": "other"},
        "predicate": {**rule, "predicate": "wrong"},
        "priority": {**rule, "priority": -1},
        "subjects": {**rule, "subjects": []},
        "extra": {**rule, "extra": True},
        "live_empty": {**rule, "status": "approved", "enforcement": "none", "subjects": {}},
    }
    for value in cases.values():
        source = {"audit_review_rules": {"audit_fixture": value}, "slot_policy_evidence": {"src": {}}}
        policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError):
            generate_module._load_audit_review_rules(
                ontology_root,
                {
                    "catalogs": [
                        {
                            "id": "policies",
                            "role": "policies",
                            "path": "ontology/policies.yaml",
                            "root_class": "SchedulingPolicyCatalog",
                        }
                    ]
                },
            )
    for rule_id, raw_rule in [("bad_id", rule), ("audit_bad", "not-a-map")]:
        source = {"audit_review_rules": {rule_id: raw_rule}, "slot_policy_evidence": {"src": {}}}
        policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError):
            generate_module._load_audit_review_rules(
                ontology_root,
                {
                    "catalogs": [
                        {
                            "id": "policies",
                            "role": "policies",
                            "path": "ontology/policies.yaml",
                            "root_class": "SchedulingPolicyCatalog",
                        }
                    ]
                },
            )
    for subjects in [{"bad": {"disposition": "governed_assignment"}}, {"sub_fixture": "bad"}]:
        live = {
            **rule,
            "status": "review_pending",
            "enforcement": "advisory",
            "subjects": subjects,
            "evidence_gap": "pending",
        }
        source = {"audit_review_rules": {"audit_fixture": live}, "slot_policy_evidence": {"src": {}}}
        policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError):
            generate_module._load_audit_review_rules(
                ontology_root,
                {
                    "catalogs": [
                        {
                            "id": "policies",
                            "role": "policies",
                            "path": "ontology/policies.yaml",
                            "root_class": "SchedulingPolicyCatalog",
                        }
                    ]
                },
            )
    source = {"audit_review_rules": {"audit_fixture": rule}, "slot_policy_evidence": {"src": {}}}
    policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    assert generate_module._load_audit_review_rules(
        ontology_root,
        {
            "catalogs": [
                {
                    "id": "policies",
                    "role": "policies",
                    "path": "ontology/policies.yaml",
                    "root_class": "SchedulingPolicyCatalog",
                }
            ]
        },
    )


def test_every_manifest_source_contributes_to_source_hash_and_compile_is_write_free(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    baseline = generate_module.compile_ontology(copied)
    baseline_runtime = _object_mapping(_loaded_yaml(baseline[Path("runtime-vocabulary.yaml")]))
    generated_before = {
        p.relative_to(copied / "generated"): p.read_bytes() for p in (copied / "generated").rglob("*") if p.is_file()
    }
    manifest = _object_mapping(_loaded_yaml((copied / "manifest.yaml").read_text(encoding="utf-8")))
    sources = [_string(manifest["linkml_root"]), *_string_list(manifest["linkml_modules"])]
    sources.extend(_string(item["path"]) for item in _mapping_list(manifest["catalogs"]))
    for relative in sources:
        target = copied.parent / relative
        original = target.read_bytes()
        target.write_bytes(original + b"\n# adversarial source mutation\n")
        mutated = generate_module.compile_ontology(copied)
        runtime = _object_mapping(_loaded_yaml(mutated[Path("runtime-vocabulary.yaml")]))
        assert runtime["source_hash"] != baseline_runtime["source_hash"], relative
        target.write_bytes(original)
    assert {
        p.relative_to(copied / "generated"): p.read_bytes() for p in (copied / "generated").rglob("*") if p.is_file()
    } == generated_before


@pytest.mark.parametrize(
    "field,value",
    [
        ("linkml_root", "ontology/./supp_slotter.yaml"),
        ("linkml_root", "ontology/../ontology/supp_slotter.yaml"),
        ("linkml_root", "ontology/*.yaml"),
        ("linkml_root", "ontology/generated/supp_slotter.yaml"),
    ],
)
def test_manifest_source_paths_are_canonical_and_fail_closed(tmp_path: Path, field: str, value: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = _object_mapping(_loaded_yaml(manifest_path.read_text(encoding="utf-8")))
    manifest[field] = value
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_manifest_rejects_duplicate_root_and_symlinked_sources(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = _object_mapping(_loaded_yaml(manifest_path.read_text(encoding="utf-8")))
    modules = _string_list(manifest["linkml_modules"])
    modules.append(_string(manifest["linkml_root"]))
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)
    modules.pop()
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    source = copied.parent / modules[0]
    source.unlink()
    source.symlink_to(ROOT / modules[0])
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


@pytest.mark.parametrize(
    "raw",
    [
        "./card.schema.json",
        "nested//card.schema.json",
        "card.schema.json/",
        "../card.schema.json",
        "ontology/card.schema.json",
        "generated/card.schema.json",
        "/tmp/card.schema.json",
        "card*.schema.json",
    ],
)
def test_artifact_manifest_rejects_unsafe_raw_paths(tmp_path: Path, raw: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = _object_mapping(_loaded_yaml(manifest_path.read_text(encoding="utf-8")))
    manifest["artifacts"] = [raw]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_artifact_manifest_rejects_duplicate_paths() -> None:
    manifest = {"artifacts": ["card.schema.json", "card.schema.json"]}
    with pytest.raises(OntologyInfrastructureError):
        generate_module._validate_artifact_manifest(manifest)


@pytest.mark.parametrize(
    "raw",
    [
        "ontology/./vocabulary.yaml",
        "ontology//vocabulary.yaml",
        "ontology/vocabulary.yaml/",
        "ontology/../ontology/vocabulary.yaml",
        "ontology/generated/vocabulary.yaml",
        "/tmp/vocabulary.yaml",
    ],
)
def test_catalog_paths_use_strict_shared_resolver(tmp_path: Path, raw: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = _object_mapping(_loaded_yaml(manifest_path.read_text(encoding="utf-8")))
    catalogs = _mapping_list(manifest["catalogs"])
    catalogs[0]["path"] = raw
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_catalog_paths_reject_logical_and_resolved_duplicates(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = _object_mapping(_loaded_yaml(manifest_path.read_text(encoding="utf-8")))
    catalogs = _mapping_list(manifest["catalogs"])
    catalogs[1]["path"] = catalogs[0]["path"]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_catalog_paths_reject_symlink_aliases(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = _object_mapping(_loaded_yaml(manifest_path.read_text(encoding="utf-8")))
    catalogs = _mapping_list(manifest["catalogs"])
    target = copied.parent / _string(catalogs[0]["path"])
    target.unlink()
    target.symlink_to(ROOT / _string(catalogs[0]["path"]))
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_check_rejects_modified_missing_extra_and_symlinked_outputs(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    generate_module.generate_ontology(copied)
    artifacts = generate_module.compile_ontology(copied)
    generated = copied / "generated"
    (generated / "card.schema.json").write_bytes(b"modified")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.check_artifacts(copied, artifacts)
    generate_module.generate_ontology(copied)
    (generated / "extra.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.check_artifacts(copied, artifacts)
    (generated / "extra.txt").unlink()
    (generated / "card.schema.json").unlink()
    with pytest.raises(OntologyInfrastructureError):
        generate_module.check_artifacts(copied, artifacts)
    (generated / "card.schema.json").symlink_to(generated / "ontology.ttl")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.check_artifacts(copied, artifacts)


def test_second_rename_failure_restores_original_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copied = _copy_repository_shape(tmp_path)
    artifacts = generate_module.compile_ontology(copied)
    generated = copied / "generated"
    before = {p.relative_to(generated): p.read_bytes() for p in generated.rglob("*") if p.is_file()}
    real_replace = os.replace
    calls = 0

    def fail_second(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second rename failure")
        real_replace(source, destination)

    monkeypatch.setattr(generate_module.os, "replace", fail_second)
    with pytest.raises(OSError, match="second rename"):
        generate_module.write_artifacts(copied, artifacts)
    assert {p.relative_to(generated): p.read_bytes() for p in generated.rglob("*") if p.is_file()} == before
