"""Closed repository projection contracts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

import pytest
import yaml
from planner.ontology.errors import OntologyInfrastructureError
from scripts.ontology_compiler import compile_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"


def _fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    shutil.copytree(ONTOLOGY, repository / "ontology")
    shutil.copytree(ROOT / "data", repository / "data")
    return repository / "ontology"


def _manifest(path: Path) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def test_projection_sources_are_closed_and_canonical() -> None:
    projection = cast(dict[str, object], _manifest(ONTOLOGY / "manifest.yaml")["repository_projection"])
    assert set(projection) == {"format_version", "base_iri", "sources", "mappings"}
    assert projection["format_version"] == "repository-projection-v1"
    assert cast(list[dict[str, object]], projection["sources"]) == [
        {
            "id": "substances",
            "locator": {"kind": "flat_root", "path": "data/substances"},
            "root_class": "Substance",
        },
        {
            "id": "products",
            "locator": {"kind": "flat_root", "path": "data/products"},
            "root_class": "Product",
        },
        {
            "id": "dashboards",
            "locator": {"kind": "flat_root", "path": "data/dashboards"},
            "root_class": "Dashboard",
        },
        {
            "id": "stacks",
            "locator": {"kind": "explicit_path", "path": "data/stacks.yaml"},
            "root_class": "Stack",
        },
        {
            "id": "pillboxes",
            "locator": {"kind": "explicit_path", "path": "data/pillboxes.yaml"},
            "root_class": "Pillbox",
        },
        {"id": "assertions", "locator": {"kind": "catalog_ref", "catalog_id": "assertions"}},
    ]


def test_projection_source_with_unknown_field_fails_closed(tmp_path: Path) -> None:
    ontology = _fixture(tmp_path)
    manifest_path = ontology / "manifest.yaml"
    manifest = _manifest(manifest_path)
    projection = cast(dict[str, object], manifest["repository_projection"])
    sources = cast(list[dict[str, object]], projection["sources"])
    sources[0]["unexpected"] = True
    _write_manifest(manifest_path, manifest)

    with pytest.raises(OntologyInfrastructureError, match="unsupported fields"):
        compile_ontology(ontology)
