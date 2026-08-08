"""Fail-closed tests for direct runtime scheduling semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import compile_ontology

from tests.test_ontology_artifacts import _copy_repository_shape


def _load(path: Path) -> dict[str, object]:
    value = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def test_invalid_runtime_policy_fails_closed(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "runtime-policy.yaml"
    source = _load(path)
    source.pop("effect_scoring")
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(root)


def test_direct_runtime_projection_contains_effects_scores_and_constraints(tmp_path: Path) -> None:
    artifacts = compile_ontology(_copy_repository_shape(tmp_path))
    runtime = cast(dict[str, object], json.loads(artifacts[Path("runtime-program.json")]))
    projection = cast(dict[str, object], runtime["projection"])
    assert "effect_scoring" in projection
    assert "prefer_with_policy" in projection
    constraints = cast(list[dict[str, object]], projection["constraint_execution_policies"])
    assert {row["operation"] for row in constraints} == {"separate_products_same_slot"}
