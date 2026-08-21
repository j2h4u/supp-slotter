"""Duplicate YAML keys fail closed at every production read boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from planner.contracts import CardLoadError
from planner.ontology.artifacts import _decode_artifact
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.projection import _project_repository_with_projection
from planner.yaml_io import DuplicateYamlKeyError, load_yaml, safe_load_yaml
from scripts.ontology_compiler import compile_ontology

from tests.test_ontology_repository_projection import _map, _repo


def test_loader_reports_top_level_and_nested_duplicate_keys() -> None:
    with pytest.raises(DuplicateYamlKeyError, match=r"fixture.yaml:2:1: duplicate YAML key 'id'"):
        safe_load_yaml("id: first\nid: second\n", path=Path("fixture.yaml"))

    with pytest.raises(DuplicateYamlKeyError, match=r"fixture.yaml:4:3: duplicate YAML key 'id'.*substance"):
        safe_load_yaml(
            "substance:\n  name: Example\n  id: first\n  id: second\n",
            path=Path("fixture.yaml"),
        )


def test_card_loader_wraps_nested_duplicate_as_controlled_error(tmp_path: Path) -> None:
    path = tmp_path / "substance.yaml"
    path.write_text("id: sub_example\nmetadata:\n  label: one\n  label: two\n", encoding="utf-8")

    with pytest.raises(CardLoadError, match=r"substance\.yaml:4:3: duplicate YAML key 'label'"):
        load_yaml(path)


def test_repository_relation_and_stack_documents_reject_duplicate_keys(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "data/relations.yaml").write_text(
        "relations:\n  - id: rel_1\n    selector:\n      source: one\n      source: two\n",
        encoding="utf-8",
    )
    with pytest.raises(OntologyInfrastructureError, match=r"duplicate YAML key 'source'"):
        _project_repository_with_projection(repo, _map())

    repo = _repo(tmp_path / "stack")
    (repo / "data/stacks.yaml").write_text("daily: [prd_p]\ndaily: [prd_p]\n", encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match=r"duplicate YAML key 'daily'"):
        _project_repository_with_projection(repo, _map())


def test_generated_yaml_artifact_decoder_rejects_duplicate_catalog_key() -> None:
    with pytest.raises(OntologyInfrastructureError, match=r"catalog.yaml:2:1: duplicate YAML key 'id'"):
        _decode_artifact("runtime-vocabulary.yaml", b"id: first\nid: second\n", path=Path("catalog.yaml"))


def test_ontology_compiler_rejects_duplicate_manifest_key(tmp_path: Path) -> None:
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    manifest = ontology / "manifest.yaml"
    manifest.write_text("schema_version: 1\nschema_version: 2\n", encoding="utf-8")

    with pytest.raises(OntologyInfrastructureError, match=r"manifest\.yaml:2:1: duplicate YAML key 'schema_version'"):
        compile_ontology(ontology)
