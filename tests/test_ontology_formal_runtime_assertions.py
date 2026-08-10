"""Fail-closed tests for direct runtime scheduling semantics."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import _validate_relation_assertion_selector_forms, compile_ontology

from tests.test_ontology_artifacts import _copy_repository_shape


def _load(path: Path) -> dict[str, object]:
    value = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


@pytest.mark.parametrize("side", ["source", "target"])
def test_relation_type_selector_forms_are_executable_contract(side: str) -> None:
    source = _load(Path(__file__).resolve().parents[1] / "ontology/relations.yaml")
    relation_types = cast(list[dict[str, object]], source["relation_types"])
    supports = next(row for row in relation_types if row["id"] == "supports")
    supports[f"{side}_selector_forms"] = ["term"] if side == "source" else ["entity"]

    expected_form = "entity" if side == "source" else "term"
    with pytest.raises(OntologyInfrastructureError, match=rf"uses {expected_form} {side} selector"):
        _validate_relation_assertion_selector_forms(
            "assertion_under_test",
            supports,
            {"entity": {"entity_id": "sub_a"}},
            {"category": "kind", "term": "rigid_identity"},
        )


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
