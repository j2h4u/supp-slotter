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


@pytest.mark.parametrize(
    "mutation",
    ["duplicate_id", "empty_capability_models", "unknown_gate_state", "unknown_glue_capability"],
)
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
    elif mutation == "unknown_gate_state":
        gate = cast(list[dict[str, object]], source["execution_gates"])[0]
        gate["lifecycle_state"] = "missing_state"
    else:
        contract = cast(dict[str, object], source["glue_contract"])
        adapters = cast(list[str], contract["scope_fact_adapters"])
        adapters.append("unknown_adapter")

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
