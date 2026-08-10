"""Fail-closed tests for direct runtime scheduling semantics."""

from __future__ import annotations

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


@pytest.mark.parametrize("effect_fields", [{"match": {"food": True}}, {"match": {"food": True}, "block": True}])
def test_policy_effect_requires_level_and_rejects_block(tmp_path: Path, effect_fields: dict[str, object]) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root / "policies.yaml"
    source = _load(path)
    policies = cast(dict[str, object], source["scheduling_policies"])
    first_policy = cast(dict[str, object], next(iter(policies.values())))
    effects = cast(list[object], first_policy["effects"])
    effects[0] = effect_fields
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError):
        compile_ontology(root)


@pytest.mark.parametrize("side", ["source", "target"])
def test_relation_type_selector_forms_are_executable_contract(tmp_path: Path, side: str) -> None:
    root = _copy_repository_shape(tmp_path)
    relation_model = root / "relations.yaml"
    source = _load(relation_model)
    relation_types = cast(list[dict[str, object]], source["relation_types"])
    supports = next(row for row in relation_types if row["id"] == "supports")
    supports[f"{side}_selector_forms"] = ["term"] if side == "source" else ["entity"]
    relation_model.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    expected_form = "entity" if side == "source" else "term"
    with pytest.raises(OntologyInfrastructureError, match=rf"uses {expected_form} {side} selector"):
        compile_ontology(root)


def test_directionless_relation_rejects_reversed_duplicate(tmp_path: Path) -> None:
    root = _copy_repository_shape(tmp_path)
    path = root.parent / "data/relations.yaml"
    source = _load(path)
    relations = cast(list[dict[str, object]], source["relations"])
    original = next(row for row in relations if row["relation_type"] == "balance")
    duplicate = dict(original)
    duplicate["id"] = "rel_balance_reversed_duplicate"
    duplicate["source_selector"], duplicate["target_selector"] = (
        original["target_selector"],
        original["source_selector"],
    )
    relations.append(duplicate)
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match="non-directional relation type 'balance'"):
        compile_ontology(root)
