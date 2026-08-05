"""Fail-closed tests for the authored runtime-policy contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import compile_ontology

from tests.test_ontology_artifacts import _copy_repository_shape


def _runtime_policy(root: Path) -> Path:
    return root / "runtime-policy.yaml"


def _scheduling_constraints(root: Path) -> Path:
    return root / "scheduling-constraints.yaml"


def _load(path: Path) -> dict[str, object]:
    value = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _write(path: Path, value: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


@pytest.mark.parametrize("mutation", ["duplicate_id", "empty_capability_models", "unknown_gate_state"])
def test_invalid_runtime_policy_fails_closed(tmp_path: Path, mutation: str) -> None:
    root = _copy_repository_shape(tmp_path)
    path = _runtime_policy(root)
    source = _load(path)

    if mutation == "duplicate_id":
        rows = cast(list[dict[str, object]], source["execution_gates"])
        rows.append(dict(rows[0]))
    elif mutation == "empty_capability_models":
        capability = cast(list[dict[str, object]], source["capability_rules"])[0]
        capability["slot_models"] = []
    else:
        gate = cast(list[dict[str, object]], source["execution_gates"])[0]
        gate["lifecycle_state"] = "missing_state"

    _write(path, source)
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(root)


def test_runtime_policy_cross_references_and_nonempty_program_survive_compilation(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    source = _load(_runtime_policy(root))
    artifacts = compile_ontology(root)
    runtime = cast(dict[str, object], yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")]))
    policy = cast(dict[str, object], runtime["runtime_policy"])

    lifecycle_states = {row["state"] for row in cast(list[dict[str, object]], source["lifecycle_policies"])}
    gates = cast(list[dict[str, object]], policy["execution_gates"])
    assert gates and all(row["lifecycle_state"] in lifecycle_states for row in gates)
    capabilities = cast(list[dict[str, object]], policy["capability_rules"])
    assert capabilities and all(cast(list[object], row["near_to_model"]) for row in capabilities)


def test_constraint_metadata_and_evidence_format_follow_authored_sources(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    policy_path = _runtime_policy(root)
    policy = _load(policy_path)
    governance = cast(dict[str, object], policy["constraint_governance"])
    evidence_format = cast(dict[str, object], governance["evidence_format"])
    evidence_format["scheme"] = "http"

    constraints_path = _scheduling_constraints(root)
    constraints = _load(constraints_path)
    rows = cast(dict[str, dict[str, object]], constraints["scheduling_constraints"])
    for row in rows.values():
        row["assertion_type"] = "authored_constraint_kind"
        evidence = cast(list[object], row["evidence"])
        row["evidence"] = [item.replace("https://", "http://") for item in evidence if isinstance(item, str)]

    _write(policy_path, policy)
    _write(constraints_path, constraints)
    artifacts = compile_ontology(root)
    runtime = cast(dict[str, object], yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")]))
    projected = cast(dict[str, dict[str, object]], runtime["scheduling_constraints"])
    runtime_program = cast(dict[str, object], json.loads(artifacts[Path("runtime-program.json")]))
    projection = cast(dict[str, object], runtime_program["projection"])
    program_governance = cast(dict[str, object], projection["constraint_governance"])

    assert projected
    assert all(row["assertion_type"] == "authored_constraint_kind" for row in projected.values())
    assert all(
        all(isinstance(item, str) and item.startswith("http://") for item in cast(list[object], row["evidence"]))
        for row in projected.values()
    )
    assert program_governance["evidence_format"] == evidence_format


def test_scheduling_constraint_projection_preserves_authored_key_order(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = _scheduling_constraints(root)
    source = _load(path)
    rows = cast(dict[str, dict[str, object]], source["scheduling_constraints"])
    authored_order = list(rows)

    artifacts = compile_ontology(root)
    runtime = cast(dict[str, object], yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")]))
    projected = cast(dict[str, dict[str, object]], runtime["scheduling_constraints"])
    assert list(projected) == authored_order

    reordered = list(reversed(list(rows.items())))
    rows.clear()
    rows.update(reordered)
    _write(path, source)
    artifacts = compile_ontology(root)
    runtime = cast(dict[str, object], yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")]))
    projected = cast(dict[str, dict[str, object]], runtime["scheduling_constraints"])
    assert list(projected) == list(rows)


def test_scheduling_constraint_catalog_acceptance_is_authored_schema_driven(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    constraints_path = _scheduling_constraints(root)
    constraints = _load(constraints_path)
    rows = cast(dict[str, dict[str, object]], constraints["scheduling_constraints"])
    first = next(iter(rows.values()))
    first["authored_extension"] = "accepted-after-schema-edit"
    _write(constraints_path, constraints)

    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(root)

    model_path = root / "scheduling-model.yaml"
    model = model_path.read_text(encoding="utf-8")
    class_marker = "      - semantic_note\n      - action\n    slot_usage:"
    assert model.count(class_marker) == 1
    model = model.replace(
        class_marker,
        "      - semantic_note\n      - action\n      - authored_extension\n    slot_usage:",
        1,
    )
    slot_marker = "  legacy_relation_id:\n"
    assert model.count(slot_marker) == 1
    model = model.replace(
        "  legacy_relation_id:\n", "  authored_extension:\n    range: string\n  legacy_relation_id:\n", 1
    )
    model_path.write_text(model, encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="unconsumed_authored_field"):
        compile_ontology(root)


@pytest.mark.parametrize(("require_host", "should_raise"), [(True, True), (False, False)])
def test_constraint_evidence_host_requirement_is_authored_and_fail_closed(
    tmp_path: Path, require_host: bool, should_raise: bool
) -> None:
    root = _copy_repository_shape(tmp_path)
    policy_path = _runtime_policy(root)
    policy = _load(policy_path)
    governance = cast(dict[str, object], policy["constraint_governance"])
    evidence_format = cast(dict[str, object], governance["evidence_format"])
    evidence_format["require_host"] = require_host

    constraints_path = _scheduling_constraints(root)
    constraints = _load(constraints_path)
    rows = cast(dict[str, dict[str, object]], constraints["scheduling_constraints"])
    evidence = cast(list[object], next(iter(rows.values()))["evidence"])
    evidence[0] = "https://:443/path"
    _write(policy_path, policy)
    _write(constraints_path, constraints)

    if should_raise:
        with pytest.raises(OntologyInfrastructureError):
            compile_ontology(root)
    else:
        artifacts = compile_ontology(root)
        runtime = cast(dict[str, object], yaml.safe_load(artifacts[Path("runtime-vocabulary.yaml")]))
        projected = cast(dict[str, dict[str, object]], runtime["scheduling_constraints"])
        projected_row = next(iter(projected.values()))
        assert cast(list[object], projected_row["evidence"])[0] == "https://:443/path"
