"""v2 ontology artifact and fail-closed generator contract."""

import os
import shutil
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.artifacts import load_runtime_vocabulary
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.runtime_contract import runtime_assertions, validate_runtime_assertions
from scripts import ontology_compiler as generate_module
from scripts.ontology_compiler import generate_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _copy_repository_shape(tmp_path: Path) -> Path:
    """Create a repository-shaped fixture matching manifest repo-relative paths."""
    repository = tmp_path / "repo"
    copied_ontology = repository / "ontology"
    shutil.copytree(ONTOLOGY, copied_ontology)
    manifest = cast(dict[str, object], yaml.safe_load((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    fields = ("linkml_root", "linkml_modules", "policy_sources", "constraint_sources", "assertion_sources", "custom_shapes")
    paths: set[str] = set()
    for field in fields:
        value = manifest.get(field)
        if isinstance(value, str):
            paths.add(value)
        elif isinstance(value, list):
            paths.update(item for item in value if isinstance(item, str))
    for catalog in manifest.get("catalogs", []):
        if isinstance(catalog, dict) and isinstance(catalog.get("path"), str):
            paths.add(catalog["path"])
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
        assertions["scope_allowlist"] = list(reversed(cast(list[str], assertions["scope_allowlist"])))
    elif case == "diagnosis":
        values = cast(list[str], assertions["scope_allowlist"])
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
    runtime = cast(dict[str, object], yaml.safe_load(runtime_path.read_text(encoding="utf-8")))
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
    raw = cast(dict[str, object], yaml.safe_load(runtime.read_text(encoding="utf-8")))
    raw["format"] = "supp-slotter.runtime-vocabulary/v1"
    runtime.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        load_runtime_vocabulary(copied)


@pytest.mark.parametrize("field", ["status", "enforcement", "scope", "evidence", "owner", "review_by"])
def test_missing_policy_governance_fails_closed(tmp_path: Path, field: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    policy_path = copied / "policies.yaml"
    authored = cast(dict[str, object], yaml.safe_load(policy_path.read_text(encoding="utf-8")))
    policy = cast(dict[str, object], cast(dict[str, object], authored["scheduling_policies"])["intake:food_preferred"])
    policy.pop(field, None)
    policy_path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_ontology(copied)


def test_invalid_pending_block_and_retired_effects_fail(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    path = copied / "policies.yaml"
    authored = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    policies = cast(dict[str, object], authored["scheduling_policies"])
    pending = cast(dict[str, object], policies["activity:post_workout"])
    pending["enforcement"] = "block"
    path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_ontology(copied)


def test_evidence_catalog_rejects_empty_authoritative_text(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    path = copied / "policies.yaml"
    authored = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    catalog = cast(dict[str, object], authored["slot_policy_evidence"])
    evidence = cast(dict[str, object], catalog["enzyme.E5"])
    evidence["supports"] = ""
    path.write_text(yaml.safe_dump(authored, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="supports"):
        generate_ontology(copied)


def test_governance_normalization_helpers_preserve_contract() -> None:
    catalog = {"src": {"kind": "operational_contract"}}
    raw = {
        "status": "approved",
        "enforcement": "none",
        "scope": {"planner": "audit"},
        "evidence": [{"source": "src", "supports": "claim", "limitations": "limit"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    result = generate_module._normalize_record_governance("fixture", cast(dict[str, object], raw), catalog, effects=[])
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
    raw = {
        "status": "approved",
        "enforcement": "none",
        "scope": {"planner": "audit"},
        "evidence": [{"source": "src", "supports": "claim", "limitations": "limit"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    raw[field] = value
    with pytest.raises(OntologyInfrastructureError, match=message):
        generate_module._normalize_record_governance("fixture", cast(dict[str, object], raw), {"src": {}}, effects=[])


def test_governance_lifecycle_rejects_pending_block_and_retired_effects() -> None:
    base = {
        "status": "review_pending",
        "enforcement": "block",
        "scope": {"planner": "audit"},
        "evidence": [],
        "evidence_gap": "needs review",
        "owner": "team",
        "review_by": "2026-12-31",
    }
    with pytest.raises(OntologyInfrastructureError, match="cannot block"):
        generate_module._normalize_record_governance("fixture", cast(dict[str, object], base), {}, effects=[])
    retired = {**base, "status": "retired", "enforcement": "none"}
    with pytest.raises(OntologyInfrastructureError, match="retired records"):
        generate_module._normalize_record_governance(
            "fixture", cast(dict[str, object], retired), {}, effects=[{"block": True}]
        )


def test_audit_subject_shapes_and_evidence_validation() -> None:
    catalog: dict[str, object] = {"src": {}}
    assert generate_module._normalize_audit_subject("audit_x", {"disposition": "governed_assignment"}, catalog)
    reviewed = {
        "disposition": "reviewed_no_assignment",
        "status": "review_pending",
        "scope": {"planner": "audit"},
        "evidence": [],
        "evidence_gap": "pending",
        "owner": "team",
        "review_by": "2026-12-31",
    }
    assert (
        generate_module._normalize_audit_subject("audit_x", cast(dict[str, object], reviewed), catalog)["status"]
        == "review_pending"
    )
    for evidence in [["bad"], [{"source": "missing", "supports": "x", "limitations": "y"}], [{"source": "src"}]]:
        with pytest.raises(OntologyInfrastructureError):
            generate_module._validate_evidence_entries("fixture", cast(list[object], evidence), catalog)

    invalid = [
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
            generate_module._normalize_audit_subject("audit_x", cast(dict[str, object], item), catalog)


def test_scheduling_constraint_normalizes_optional_fields() -> None:
    raw = {
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
    normalized = generate_module._normalize_scheduling_constraint("sc_fixture", cast(dict[str, object], raw), set())
    assert normalized["semantic_note"] == "fixture note"
    assert normalized["action"] == "fixture action"
    for key, value in {
        "assertion_type": "wrong",
        "effect": "wrong",
        "enforcement": "none",
        "semantic_note": "",
        "action": "",
    }.items():
        invalid = {**raw, key: value}
        with pytest.raises(OntologyInfrastructureError):
            generate_module._normalize_scheduling_constraint("sc_fixture", cast(dict[str, object], invalid), set())


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
                {"catalogs": [{"id": "policies", "role": "policies", "path": "ontology/policies.yaml", "root_class": "SchedulingPolicyCatalog"}]},
            )
    for rule_id, raw_rule in [("bad_id", rule), ("audit_bad", "not-a-map")]:
        source = {"audit_review_rules": {rule_id: raw_rule}, "slot_policy_evidence": {"src": {}}}
        policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError):
            generate_module._load_audit_review_rules(
                ontology_root,
                {"catalogs": [{"id": "policies", "role": "policies", "path": "ontology/policies.yaml", "root_class": "SchedulingPolicyCatalog"}]},
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
            generate_module._load_audit_review_rules(ontology_root, {"catalogs": [{"id": "policies", "role": "policies", "path": "ontology/policies.yaml", "root_class": "SchedulingPolicyCatalog"}]})
    source = {"audit_review_rules": {"audit_fixture": rule}, "slot_policy_evidence": {"src": {}}}
    policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    assert generate_module._load_audit_review_rules(ontology_root, {"catalogs": [{"id": "policies", "role": "policies", "path": "ontology/policies.yaml", "root_class": "SchedulingPolicyCatalog"}]})


def test_every_manifest_source_contributes_to_source_hash_and_compile_is_write_free(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    baseline = generate_module.compile_ontology(copied)
    baseline_runtime = cast(dict[str, object], yaml.safe_load(baseline[Path("runtime-vocabulary.yaml")]))
    generated_before = {p.relative_to(copied / "generated"): p.read_bytes() for p in (copied / "generated").rglob("*") if p.is_file()}
    manifest = cast(dict[str, object], yaml.safe_load((copied / "manifest.yaml").read_text(encoding="utf-8")))
    sources = [cast(str, manifest["linkml_root"]), *cast(list[str], manifest["linkml_modules"])]
    sources.extend(cast(str, item["path"]) for item in cast(list[dict[str, object]], manifest["catalogs"]))
    for relative in sources:
        target = copied.parent / relative
        original = target.read_bytes()
        target.write_bytes(original + b"\n# adversarial source mutation\n")
        mutated = generate_module.compile_ontology(copied)
        runtime = cast(dict[str, object], yaml.safe_load(mutated[Path("runtime-vocabulary.yaml")]))
        assert runtime["source_hash"] != baseline_runtime["source_hash"], relative
        target.write_bytes(original)
    assert {p.relative_to(copied / "generated"): p.read_bytes() for p in (copied / "generated").rglob("*") if p.is_file()} == generated_before


@pytest.mark.parametrize("field,value", [
    ("linkml_root", "ontology/./supp_slotter.yaml"),
    ("linkml_root", "ontology/../ontology/supp_slotter.yaml"),
    ("linkml_root", "ontology/*.yaml"),
    ("linkml_root", "ontology/generated/supp_slotter.yaml"),
])
def test_manifest_source_paths_are_canonical_and_fail_closed(tmp_path: Path, field: str, value: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = cast(dict[str, object], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    manifest[field] = value
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_manifest_rejects_duplicate_root_and_symlinked_sources(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = cast(dict[str, object], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    modules = cast(list[str], manifest["linkml_modules"])
    modules.append(cast(str, manifest["linkml_root"]))
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


@pytest.mark.parametrize("raw", [
    "./card.schema.json",
    "nested//card.schema.json",
    "card.schema.json/",
    "../card.schema.json",
    "ontology/card.schema.json",
    "generated/card.schema.json",
    "/tmp/card.schema.json",
    "card*.schema.json",
])
def test_artifact_manifest_rejects_unsafe_raw_paths(tmp_path: Path, raw: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = cast(dict[str, object], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    manifest["artifacts"] = [raw]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_artifact_manifest_rejects_duplicate_paths() -> None:
    manifest = {"artifacts": ["card.schema.json", "card.schema.json"]}
    with pytest.raises(OntologyInfrastructureError):
        generate_module._validate_artifact_manifest(manifest)


@pytest.mark.parametrize("raw", [
    "ontology/./vocabulary.yaml",
    "ontology//vocabulary.yaml",
    "ontology/vocabulary.yaml/",
    "ontology/../ontology/vocabulary.yaml",
    "ontology/generated/vocabulary.yaml",
    "/tmp/vocabulary.yaml",
])
def test_catalog_paths_use_strict_shared_resolver(tmp_path: Path, raw: str) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = cast(dict[str, object], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    catalogs = cast(list[dict[str, object]], manifest["catalogs"])
    catalogs[0]["path"] = raw
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_catalog_paths_reject_logical_and_resolved_duplicates(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = cast(dict[str, object], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    catalogs = cast(list[dict[str, object]], manifest["catalogs"])
    catalogs[1]["path"] = catalogs[0]["path"]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.compile_ontology(copied)


def test_catalog_paths_reject_symlink_aliases(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest = cast(dict[str, object], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    catalogs = cast(list[dict[str, object]], manifest["catalogs"])
    target = copied.parent / cast(str, catalogs[0]["path"])
    target.unlink()
    target.symlink_to(ROOT / cast(str, catalogs[0]["path"]))
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
