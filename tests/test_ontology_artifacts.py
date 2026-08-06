"""v2 ontology artifact and fail-closed generator contract."""

# pyright: reportAny=false

import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Never, TypeGuard, cast

import pytest
import yaml
from planner.ontology.artifacts import load_runtime_vocabulary
from planner.ontology.errors import MALFORMED, OntologyInfrastructureError
from planner.ontology.runtime_program import RELATION_WARNING_ACTIVE_SIDES, RELATION_WARNING_FILTER_FIELDS
from scripts import ontology_compiler as generate_module
from scripts.ontology_compiler import generate_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"

_COMPILE_FRAME_VERSION = "supp-slotter.test-compile-runtime/v1"
# Normal compiles take about 14s; 60s gives more than 2x headroom over the
# previously observed 24.5s slow leaf while still bounding a wedged child.
_ONTOLOGY_COMPILE_TIMEOUT_SECONDS = 60.0
_COMPILE_DIAGNOSTIC_LIMIT_BYTES = 8_192
_COMPILE_RUNTIME_WORKER = """
import base64
import hashlib
import json
import sys
from pathlib import Path

from scripts.ontology_compiler import compile_ontology

payload = compile_ontology(Path(sys.argv[1]))[Path("runtime-vocabulary.yaml")]
frame = {
    "version": "supp-slotter.test-compile-runtime/v1",
    "payload_base64": base64.b64encode(payload).decode("ascii"),
    "byte_length": len(payload),
    "sha256": hashlib.sha256(payload).hexdigest(),
}
sys.stdout.write(json.dumps(frame, separators=(",", ":"), sort_keys=True))
sys.stdout.write("\\n")
"""

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


def _runtime_policy_fixture() -> generate_module._PolicyRuntime:
    """Load the authored runtime policy through the production parser."""
    manifest = _object_mapping(_loaded_yaml((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    schema_view = generate_module._schema_view(ONTOLOGY, manifest)
    relation_types = generate_module._load_relation_types(ONTOLOGY, manifest, schema_view)
    return generate_module._load_runtime_policy(ONTOLOGY, manifest, schema_view, set(relation_types))


def test_relation_type_order_is_authored_by_catalog_not_name_sort() -> None:
    manifest = _object_mapping(_loaded_yaml((ONTOLOGY / "manifest.yaml").read_text(encoding="utf-8")))
    schema_view = generate_module._schema_view(ONTOLOGY, manifest)
    relation_types = generate_module._load_relation_types(ONTOLOGY, manifest, schema_view)

    assert list(relation_types) == ["balance", "supports", "review_with"]
    assert [relation_types[relation_type]["order"] for relation_type in relation_types] == [10, 20, 30]


def test_relation_warning_runtime_sets_match_authored_protocol_enums() -> None:
    protocol = _object_mapping(_loaded_yaml((ONTOLOGY / "runtime-protocol.yaml").read_text(encoding="utf-8")))
    enums = _object_mapping(protocol["enums"])

    filter_field_enum = _object_mapping(_object_mapping(enums["RelationWarningFilterField"])["permissible_values"])
    active_side_enum = _object_mapping(_object_mapping(enums["RelationWarningActiveSide"])["permissible_values"])

    assert set(filter_field_enum) == RELATION_WARNING_FILTER_FIELDS
    assert set(active_side_enum) == RELATION_WARNING_ACTIVE_SIDES


def test_card_and_assertion_vocabulary_enums_are_authored_in_schema() -> None:
    schema = _object_mapping(json.loads((ONTOLOGY / "generated/schema.json").read_text(encoding="utf-8")))
    definitions = _object_mapping(schema["$defs"])
    severity = _object_mapping(definitions["Severity"])
    concern_kind = _object_mapping(definitions["ConcernKind"])

    assert _string_list(severity["enum"])
    assert _string_list(concern_kind["enum"])


def _fixture_scope(policy_runtime: generate_module._PolicyRuntime) -> dict[str, str]:
    planner_key = next(key for key in policy_runtime.scope_keys if key == "planner")
    return {planner_key: sorted(policy_runtime.scope_values[planner_key])[0]}


def _fixture_lifecycle_state(
    policy_runtime: generate_module._PolicyRuntime,
    *,
    executable: bool,
    evidence_requirement: str | None = None,
) -> str:
    for state, gate in sorted(policy_runtime.execution_gates.items()):
        if gate.get("executable") is executable and (
            evidence_requirement is None or gate.get("evidence_requirement") == evidence_requirement
        ):
            return state
    raise AssertionError("authored runtime policy has no matching lifecycle state")


def _fixture_enforcement_mode(policy_runtime: generate_module._PolicyRuntime, role: str) -> str:
    return policy_runtime.enforcement_modes_by_role[role]


def _audit_review_context_fixture(catalog: dict[str, object]) -> generate_module._AuditReviewContext:
    return generate_module._AuditReviewContext(catalog, _runtime_policy_fixture())


def _record_governance_context_fixture(
    catalog: Mapping[str, object], *, effects: list[object], warning: bool
) -> generate_module._RecordGovernanceContext:
    return generate_module._RecordGovernanceContext(
        catalog=catalog,
        effects=effects,
        warning=warning,
        runtime=_governance_runtime_fixture(),
    )


def _constraint_fixture_pair(
    runtime: generate_module._ConstraintRuntime,
) -> tuple[str, str]:
    for status, gate in sorted(runtime.execution_gates.items()):
        if gate.get("executable") is not True or gate.get("evidence_requirement") != "required":
            continue
        for pair in sorted(runtime.allowed_pairs):
            if pair[0] == status:
                return pair
    raise AssertionError("authored constraint runtime has no executable governed pair")


def _governance_runtime_fixture() -> generate_module._GovernanceRuntime:
    return generate_module._governance_runtime_from_policy(_runtime_policy_fixture())


def _load_audit_review_rules_fixture(ontology_root: Path) -> list[dict[str, object]]:
    return generate_module._load_audit_review_rules(
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
        _runtime_policy_fixture(),
    )


def _loaded_yaml(source: str | bytes) -> object:
    return cast(object, yaml.safe_load(source))


def _copy_repository_shape(tmp_path: Path) -> Path:  # noqa: PLR0912
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


def _run_generator_cli(ontology_root: Path, *, check: bool = False) -> None:
    command = [
        sys.executable,
        str((ROOT / "scripts/generate_ontology.py").resolve()),
        "--ontology-root",
        str(ontology_root.resolve()),
    ]
    if check:
        command.append("--check")
    result = subprocess.run(command, capture_output=True, check=False, shell=False, text=True)
    assert result.returncode == 0, (
        f"ontology generator failed (returncode={result.returncode})\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _bounded_compile_diagnostic(value: bytes | str | None) -> str:
    if value is None:
        return "<empty>"
    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value
    if not raw:
        return "<empty>"
    if len(raw) <= _COMPILE_DIAGNOSTIC_LIMIT_BYTES:
        return raw.decode("utf-8", errors="replace")
    omitted = len(raw) - _COMPILE_DIAGNOSTIC_LIMIT_BYTES
    tail = raw[-_COMPILE_DIAGNOSTIC_LIMIT_BYTES:].decode("utf-8", errors="replace")
    return f"<truncated {omitted} leading bytes>\n{tail}"


def _fail_compile_child(
    operation: str,
    reason: str,
    *,
    stderr: bytes | str | None,
    stdout: bytes | str | None = None,
) -> Never:
    message = f"ontology compile child failed for {operation}: {reason}\nstderr:\n{_bounded_compile_diagnostic(stderr)}"
    if stdout is not None:
        message += f"\nstdout:\n{_bounded_compile_diagnostic(stdout)}"
    pytest.fail(message, pytrace=False)


def _compile_runtime_vocabulary_in_child(ontology_root: Path, *, operation: str) -> bytes:
    command = [sys.executable, "-c", _COMPILE_RUNTIME_WORKER, str(ontology_root.resolve())]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            check=False,
            shell=False,
            timeout=_ONTOLOGY_COMPILE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        _fail_compile_child(
            operation,
            f"timed out after {_ONTOLOGY_COMPILE_TIMEOUT_SECONDS:.0f}s",
            stderr=error.stderr,
            stdout=error.stdout,
        )
    if result.returncode != 0:
        reason = (
            f"terminated by signal {-result.returncode}"
            if result.returncode < 0
            else f"exited with status {result.returncode}"
        )
        _fail_compile_child(operation, reason, stderr=result.stderr, stdout=result.stdout)
    lines = result.stdout.splitlines()
    if len(lines) != 1 or result.stdout != lines[0] + b"\n":
        _fail_compile_child(
            operation,
            f"expected exactly one LF-terminated {_COMPILE_FRAME_VERSION} frame",
            stderr=result.stderr,
            stdout=result.stdout,
        )
    try:
        decoded = json.loads(lines[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail_compile_child(operation, f"malformed JSON frame: {error}", stderr=result.stderr, stdout=result.stdout)
    if not isinstance(decoded, dict):
        _fail_compile_child(operation, "JSON frame is not an object", stderr=result.stderr, stdout=result.stdout)
    frame = cast(dict[object, object], decoded)
    expected_fields = {"version", "payload_base64", "byte_length", "sha256"}
    if set(frame) != expected_fields or frame.get("version") != _COMPILE_FRAME_VERSION:
        _fail_compile_child(
            operation,
            f"invalid {_COMPILE_FRAME_VERSION} envelope",
            stderr=result.stderr,
            stdout=result.stdout,
        )
    encoded = frame["payload_base64"]
    byte_length = frame["byte_length"]
    digest = frame["sha256"]
    if not isinstance(encoded, str) or not isinstance(byte_length, int) or isinstance(byte_length, bool):
        _fail_compile_child(operation, "invalid payload metadata types", stderr=result.stderr, stdout=result.stdout)
    if not isinstance(digest, str):
        _fail_compile_child(operation, "invalid SHA-256 metadata type", stderr=result.stderr, stdout=result.stdout)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        _fail_compile_child(operation, f"invalid base64 payload: {error}", stderr=result.stderr, stdout=result.stdout)
    if byte_length < 0 or len(payload) != byte_length:
        _fail_compile_child(operation, "payload byte length mismatch", stderr=result.stderr, stdout=result.stdout)
    if hashlib.sha256(payload).hexdigest() != digest:
        _fail_compile_child(operation, "payload SHA-256 mismatch", stderr=result.stderr, stdout=result.stdout)
    return payload


def test_runtime_v2_shape_and_catalog() -> None:
    runtime = load_runtime_vocabulary(ONTOLOGY)
    assert runtime["format"] == "supp-slotter.runtime-vocabulary/v2"
    assert runtime["schema_version"] == "2"
    assert isinstance(runtime["slot_policy_evidence"], dict)
    assert isinstance(runtime["scheduling_policies"], dict)
    assert isinstance(runtime["audit_review_rules"], list)
    runtime_policy = runtime.get("runtime_policy")
    assert isinstance(runtime_policy, dict)
    assert runtime_policy
    assert "assertions" not in runtime
    assert isinstance(runtime["ontology_assertions"], dict)


def test_runtime_loader_reads_committed_projection_without_compiling(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    manifest_path = copied / "manifest.yaml"
    manifest_path.write_text("not: the compiler input\n", encoding="utf-8")
    generated_before = (copied / "generated/runtime-vocabulary.yaml").read_bytes()

    with pytest.raises(OntologyInfrastructureError) as raised:
        load_runtime_vocabulary(copied)
    assert raised.value.code == MALFORMED
    assert (copied / "generated/runtime-vocabulary.yaml").read_bytes() == generated_before


def test_generation_is_deterministic_and_fresh(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    _run_generator_cli(copied)
    first = {p.name: p.read_bytes() for p in (copied / "generated").iterdir()}
    _run_generator_cli(copied)
    assert {p.name: p.read_bytes() for p in (copied / "generated").iterdir()} == first
    _run_generator_cli(copied, check=True)


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
    policy_runtime = _runtime_policy_fixture()
    status = _fixture_lifecycle_state(policy_runtime, executable=True, evidence_requirement="required")
    enforcement = _fixture_enforcement_mode(policy_runtime, "none")
    scope = _fixture_scope(policy_runtime)
    raw: dict[str, object] = {
        "status": status,
        "enforcement": enforcement,
        "scope": scope,
        "evidence": [{"source": "src", "supports": "claim", "limitations": "limit"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    result = generate_module._normalize_record_governance(
        "fixture",
        _object_mapping(raw),
        _record_governance_context_fixture(catalog, effects=[], warning=False),
    )
    assert result["status"] == status
    assert result["scope"] == scope
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
    policy_runtime = _runtime_policy_fixture()
    status = _fixture_lifecycle_state(policy_runtime, executable=True, evidence_requirement="required")
    enforcement = _fixture_enforcement_mode(policy_runtime, "none")
    scope = _fixture_scope(policy_runtime)
    if field == "enforcement":
        value = _fixture_enforcement_mode(policy_runtime, "blocking")
    raw: dict[str, object] = {
        "status": status,
        "enforcement": enforcement,
        "scope": scope,
        "evidence": [{"source": "src", "supports": "claim", "limitations": "limit"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    raw[field] = value
    with pytest.raises(OntologyInfrastructureError, match=message):
        generate_module._normalize_record_governance(
            "fixture",
            _object_mapping(raw),
            _record_governance_context_fixture({"src": {}}, effects=[], warning=False),
        )


def test_governance_lifecycle_rejects_pending_block_and_retired_effects() -> None:
    policy_runtime = _runtime_policy_fixture()
    pending = _fixture_lifecycle_state(policy_runtime, executable=True, evidence_requirement="evidence_or_gap")
    retired = _fixture_lifecycle_state(policy_runtime, executable=False)
    blocking = _fixture_enforcement_mode(policy_runtime, "blocking")
    none = _fixture_enforcement_mode(policy_runtime, "none")
    scope = _fixture_scope(policy_runtime)
    base: dict[str, object] = {
        "status": pending,
        "enforcement": blocking,
        "scope": scope,
        "evidence": [],
        "evidence_gap": "needs review",
        "owner": "team",
        "review_by": "2026-12-31",
    }
    with pytest.raises(OntologyInfrastructureError, match="enforcement does not match effects"):
        generate_module._normalize_record_governance(
            "fixture",
            _object_mapping(base),
            _record_governance_context_fixture({}, effects=[], warning=False),
        )
    retired_record: dict[str, object] = {
        **base,
        "status": retired,
        "enforcement": none,
        "evidence": [{"source": "src", "supports": "claim", "limitations": "limit"}],
    }
    with pytest.raises(OntologyInfrastructureError, match="non-executable"):
        generate_module._normalize_record_governance(
            "fixture",
            _object_mapping(retired_record),
            _record_governance_context_fixture({"src": {}}, effects=[{"block": True}], warning=False),
        )


def test_audit_subject_shapes_and_evidence_validation() -> None:
    catalog: dict[str, object] = {"src": {}}
    policy_runtime = _runtime_policy_fixture()
    context = _audit_review_context_fixture(catalog)
    expected_scope = _fixture_scope(policy_runtime)
    executable_status = _fixture_lifecycle_state(
        policy_runtime, executable=True, evidence_requirement="evidence_or_gap"
    )
    evidence_status = _fixture_lifecycle_state(policy_runtime, executable=True, evidence_requirement="required")
    assert generate_module._normalize_audit_subject(
        "audit_x",
        {"disposition": "governed_assignment"},
        context,
        expected_scope,
    )
    reviewed: dict[str, object] = {
        "disposition": "reviewed_no_assignment",
        "status": executable_status,
        "scope": expected_scope,
        "evidence": [],
        "evidence_gap": "pending",
        "owner": "team",
        "review_by": "2026-12-31",
    }
    assert (
        generate_module._normalize_audit_subject(
            "audit_x",
            _object_mapping(reviewed),
            context,
            expected_scope,
        )["status"]
        == executable_status
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
        {"disposition": "reviewed_no_assignment", "status": evidence_status, "scope": {}, "evidence": []},
        {**reviewed, "evidence": "bad"},
        {**reviewed, "status": evidence_status, "evidence": []},
        {**reviewed, "evidence": [{"source": "src", "supports": "x", "limitations": "y"}], "owner": ""},
        {**reviewed, "evidence": [{"source": "src", "supports": "x", "limitations": "y"}], "review_by": "bad"},
    ]
    for item in invalid:
        with pytest.raises(OntologyInfrastructureError):
            generate_module._normalize_audit_subject(
                "audit_x",
                _object_mapping(item),
                context,
                expected_scope,
            )


def test_scheduling_constraint_normalizes_optional_fields() -> None:
    policy_runtime = _runtime_policy_fixture()
    constraint_runtime = policy_runtime.constraints
    status, enforcement = _constraint_fixture_pair(constraint_runtime)
    invalid_enforcement = next(
        mode for mode in policy_runtime.enforcement_modes if mode not in constraint_runtime.enforcement_modes
    )
    raw: dict[str, object] = {
        "legacy_relation_id": "rel_fixture",
        "assertion_type": "clinical_scheduling_constraint",
        "operation": next(iter(constraint_runtime.execution_policies)),
        "enforcement": enforcement,
        "legacy_preserved": True,
        "status": status,
        "owner": "team",
        "review_by": "2026-12-31",
        "evidence": ["https://example.test/source"],
        "source_selector": {"entity": {"id": "sub_a"}},
        "target_selector": {"entity": {"name": "Fixture"}},
        "rationale": "fixture rationale",
        "semantic_note": "fixture note",
        "action": "fixture action",
    }
    normalized = generate_module._normalize_scheduling_constraint(
        "sc_fixture",
        _object_mapping(raw),
        set(),
        constraint_runtime,
    )
    assert normalized["semantic_note"] == "fixture note"
    assert normalized["action"] == "fixture action"
    for key, value in {
        "enforcement": invalid_enforcement,
        "semantic_note": "",
        "action": "",
    }.items():
        invalid: dict[str, object] = {**raw, key: value}
        with pytest.raises(OntologyInfrastructureError):
            generate_module._normalize_scheduling_constraint(
                "sc_fixture",
                _object_mapping(invalid),
                set(),
                constraint_runtime,
            )


def test_scheduling_constraint_loader_rejects_non_string_assertion_fields(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    source_path = copied / "scheduling-constraints.yaml"
    authored = _object_mapping(_loaded_yaml(source_path.read_text(encoding="utf-8")))
    constraints = _object_mapping(authored["scheduling_constraints"])
    constraint_id, raw_constraint = next(iter(constraints.items()))
    constraint = _object_mapping(raw_constraint)

    for field in ("assertion_type", "operation"):
        mutated = {
            **authored,
            "scheduling_constraints": {
                **constraints,
                constraint_id: {**constraint, field: []},
            },
        }
        source_path.write_text(yaml.safe_dump(mutated, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError):
            generate_module.compile_ontology(copied)


def test_audit_review_rule_loader_rejects_invalid_shapes(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    ontology_root = repository / "ontology"
    ontology_root.mkdir(parents=True)
    policy_file = ontology_root / "policies.yaml"
    policy_runtime = _runtime_policy_fixture()
    governance_runtime = generate_module._governance_runtime_from_policy(policy_runtime)
    inactive_status = _fixture_lifecycle_state(
        policy_runtime,
        executable=False,
        evidence_requirement="required",
    )
    evidence_status = _fixture_lifecycle_state(
        policy_runtime,
        executable=True,
        evidence_requirement="required",
    )
    pending_status = _fixture_lifecycle_state(
        policy_runtime,
        executable=True,
        evidence_requirement="evidence_or_gap",
    )
    quiet_enforcement = generate_module._declared_enforcement(
        [],
        False,
        governance_runtime.enforcement_modes_by_role,
    )
    warning_enforcement = generate_module._declared_enforcement(
        [],
        True,
        governance_runtime.enforcement_modes_by_role,
    )
    scope = _fixture_scope(policy_runtime)
    rule = {
        "priority": 1,
        "axis": "intake",
        "predicate": "reviewed_disposition_present",
        "subjects": {},
        "message": "fixture",
        "action": "fixture",
        "status": inactive_status,
        "enforcement": quiet_enforcement,
        "scope": scope,
        "evidence": [{"source": "src", "supports": "x", "limitations": "y"}],
        "owner": "team",
        "review_by": "2026-12-31",
    }
    cases = {
        "axis": ({**rule, "axis": "other"}, "axis is invalid"),
        "predicate": ({**rule, "predicate": "wrong"}, "predicate must be"),
        "priority": ({**rule, "priority": -1}, "priority must be"),
        "subjects": ({**rule, "subjects": []}, "subjects must be a mapping"),
        "extra": ({**rule, "extra": True}, "unsupported fields"),
        "live_empty": (
            {**rule, "status": evidence_status, "enforcement": quiet_enforcement, "subjects": {}},
            "requires live subjects",
        ),
    }
    for value, match in cases.values():
        source = {"audit_review_rules": {"audit_fixture": value}, "slot_policy_evidence": {"src": {}}}
        policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError, match=match):
            _load_audit_review_rules_fixture(ontology_root)
    for rule_id, raw_rule in [("bad_id", rule), ("audit_bad", "not-a-map")]:
        source = {"audit_review_rules": {rule_id: raw_rule}, "slot_policy_evidence": {"src": {}}}
        policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError):
            _load_audit_review_rules_fixture(ontology_root)
    for subjects in [{"bad": {"disposition": "governed_assignment"}}, {"sub_fixture": "bad"}]:
        live = {
            **rule,
            "status": pending_status,
            "enforcement": warning_enforcement,
            "subjects": subjects,
            "evidence_gap": "pending",
        }
        source = {"audit_review_rules": {"audit_fixture": live}, "slot_policy_evidence": {"src": {}}}
        policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        with pytest.raises(OntologyInfrastructureError, match="invalid subject disposition"):
            _load_audit_review_rules_fixture(ontology_root)
    source = {"audit_review_rules": {"audit_fixture": rule}, "slot_policy_evidence": {"src": {}}}
    policy_file.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    assert _load_audit_review_rules_fixture(ontology_root)


def test_every_manifest_source_contributes_to_source_hash_and_compile_is_write_free(tmp_path: Path) -> None:
    copied = _copy_repository_shape(tmp_path)
    baseline_payload = _compile_runtime_vocabulary_in_child(copied, operation="baseline")
    baseline_runtime = _object_mapping(_loaded_yaml(baseline_payload))
    manifest = _object_mapping(_loaded_yaml((copied / "manifest.yaml").read_text(encoding="utf-8")))
    baseline_source_hash = generate_module._source_hash(copied, manifest)
    assert baseline_runtime["source_hash"] == baseline_source_hash
    generated_before = {
        p.relative_to(copied / "generated"): p.read_bytes() for p in (copied / "generated").rglob("*") if p.is_file()
    }
    sources = [_string(manifest["linkml_root"]), *_string_list(manifest["linkml_modules"])]
    sources.extend(_string(item["path"]) for item in _mapping_list(manifest["catalogs"]))
    for relative in sources:
        target = copied.parent / relative
        original = target.read_bytes()
        target.write_bytes(original + b"\n# adversarial source mutation\n")
        try:
            assert generate_module._source_hash(copied, manifest) != baseline_source_hash, relative
        finally:
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
    _run_generator_cli(copied)
    generated = copied / "generated"
    artifacts: dict[Path, bytes] = {}
    for path in generated.rglob("*"):
        mode = path.lstat().st_mode
        assert not stat.S_ISLNK(mode), f"generated snapshot rejects symlink: {path}"
        if stat.S_ISDIR(mode):
            continue
        assert stat.S_ISREG(mode), f"generated snapshot rejects special node: {path}"
        artifacts[path.relative_to(generated)] = path.read_bytes()
    (generated / "card.schema.json").write_bytes(b"modified")
    with pytest.raises(OntologyInfrastructureError):
        generate_module.check_artifacts(copied, artifacts)
    _run_generator_cli(copied)
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
