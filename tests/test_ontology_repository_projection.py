"""Focused tests for compiled repository discovery and RDF projection."""

from __future__ import annotations

import copy
import gc
import json
import pickle
from dataclasses import replace
from pathlib import Path
from typing import cast

import planner.ontology.artifacts as artifacts_module
import planner.ontology.repository_sources as repository_sources_module
import pytest
from planner.ontology.artifacts import OntologyBundle, load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.projection import _project_repository_with_projection, project_repository
from planner.ontology.repository_sources import discover_repository_sources
from rdflib import URIRef

BASE = "https://example.test/ontology/"


def _map(*, explicit_paths: list[str] | None = None) -> dict[str, object]:
    sources: list[dict[str, object]] = [
        {
            "id": "substances",
            "locator": {"kind": "flat_root", "path": "data/substances"},
            "root_class": "Substance",
            "documents": {
                "document_shape": "mapping",
                "identity": {"source": "id", "predicate": BASE + "slot/id"},
                "instructions": [
                    {"kind": "slot", "source": "id", "predicate": BASE + "slot/id"},
                    {"kind": "alias", "source": "name", "predicate": BASE + "slot/label"},
                    {"kind": "sequence", "source": "aliases[]", "predicate": BASE + "slot/aliases"},
                ],
            },
        },
        {
            "id": "products",
            "locator": {"kind": "flat_root", "path": "data/products"},
            "root_class": "Product",
            "documents": {
                "document_shape": "mapping",
                "identity": {"source": "id", "predicate": BASE + "slot/id"},
                "instructions": [
                    {"kind": "slot", "source": "id", "predicate": BASE + "slot/id"},
                    {
                        "kind": "reference",
                        "source": "substance",
                        "predicate": BASE + "slot/substance",
                        "target": "Substance",
                    },
                ],
            },
        },
        {
            "id": "dashboards",
            "locator": {"kind": "flat_root", "path": "data/dashboards"},
            "root_class": "Dashboard",
            "documents": {
                "document_shape": "mapping",
                "identity": {"source": "id", "predicate": BASE + "slot/id"},
                "instructions": [{"kind": "slot", "source": "id", "predicate": BASE + "slot/id"}],
            },
        },
        {
            "id": "stacks",
            "locator": {"kind": "explicit_path", "path": "data/stacks.yaml"},
            "root_class": "Stack",
            "documents": {
                "document_shape": "keyed-map",
                "identity": {"source": "<key>", "predicate": BASE + "slot/id"},
                "instructions": [
                    {"kind": "sequence", "source": "<key>[]", "predicate": BASE + "slot/product", "target": "Product"}
                ],
            },
        },
        {
            "id": "pillboxes",
            "locator": {"kind": "explicit_path", "path": "data/pillboxes.yaml"},
            "root_class": "Pillbox",
            "documents": {
                "document_shape": "keyed-map",
                "identity": {"source": "<key>", "predicate": BASE + "slot/id"},
                "instructions": [{"kind": "slot", "source": "<key>.label", "predicate": BASE + "slot/label"}],
            },
        },
        {
            "id": "assertions",
            "locator": {"kind": "catalog_ref", "catalog_id": "assertions"},
            "root_class": "AssertionCatalog",
            "documents": {
                "document_shape": "mapping",
                "instructions": [{"kind": "slot", "source": "relations[].id", "predicate": BASE + "slot/assertion_id"}],
            },
        },
    ]
    if explicit_paths is not None:
        sources[0]["locator"] = {"kind": "explicit_paths", "paths": explicit_paths}
    return {
        "catalogs": [{"id": "assertions", "path": "data/relations.yaml"}],
        "repository_projection": {"format_version": "repository-projection-v1", "base_iri": BASE, "sources": sources},
    }


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "data/substances").mkdir(parents=True)
    (tmp_path / "data/products").mkdir()
    (tmp_path / "data/dashboards").mkdir()
    (tmp_path / "data/substances/a.yaml").write_text("id: sub_a\nname: A\naliases: [aa]\n", encoding="utf-8")
    (tmp_path / "data/products/p.yaml").write_text("id: prd_p\nsubstance: sub_a\n", encoding="utf-8")
    (tmp_path / "data/dashboards/d.yaml").write_text("id: dash_d\n", encoding="utf-8")
    (tmp_path / "data/stacks.yaml").write_text("daily: [prd_p]\n", encoding="utf-8")
    (tmp_path / "data/pillboxes.yaml").write_text("daily:\n  label: Daily\n", encoding="utf-8")
    (tmp_path / "data/relations.yaml").write_text("relations:\n- id: rel_1\n", encoding="utf-8")
    return tmp_path


def test_projection_is_deterministic_and_covers_all_source_roles(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    result_one = _project_repository_with_projection(repo, _map())
    result_two = _project_repository_with_projection(repo, _map())
    assert result_one.triples == result_two.triples
    assert result_one.canonical_ntriples == result_two.canonical_ntriples
    assert {record.source_id for record in result_one.provenance} == {
        "assertions",
        "dashboards",
        "pillboxes",
        "products",
        "stacks",
        "substances",
    }
    assert (
        URIRef(BASE + "product/prd_p"),
        URIRef(BASE + "slot/substance"),
        URIRef(BASE + "substance/sub_a"),
    ) in result_one.graph


def test_explicit_paths_are_supported_and_sorted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    extra = repo / "data/substances/b.yaml"
    extra.write_text("id: sub_b\nname: B\naliases: []\n", encoding="utf-8")
    paths = ["data/substances/b.yaml", "data/substances/a.yaml"]
    result = _project_repository_with_projection(repo, _map(explicit_paths=paths))
    assert any("sub_a" in triple[0] for triple in result.triples)
    assert any("sub_b" in triple[0] for triple in result.triples)


def test_catalog_ref_selects_declared_catalog_and_does_not_ingest_schedule(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "schedule.yaml").write_text("id: should_not_be_read\n", encoding="utf-8")
    result = _project_repository_with_projection(repo, _map())
    assert any(
        record.source_id == "assertions" and record.field_path == "relations[].id" for record in result.provenance
    )
    assert not any("should_not_be_read" in triple for triple in result.triples)


@pytest.mark.parametrize("value", [{}, []])
def test_unknown_empty_containers_fail_closed(tmp_path: Path, value: object) -> None:
    repo = _repo(tmp_path)
    (repo / "data/substances/a.yaml").write_text(
        "id: sub_a\nname: A\nunknown: " + json.dumps(value) + "\n", encoding="utf-8"
    )
    with pytest.raises(OntologyInfrastructureError, match="unknown"):
        _project_repository_with_projection(repo, _map())


def test_projector_has_no_compiler_or_linkml_imports() -> None:
    source = Path(__file__).resolve().parents[1] / "planner/ontology/projection.py"
    text = source.read_text(encoding="utf-8").lower()
    assert "linkml" not in text
    assert "ontology_compiler" not in text


def test_public_projection_and_discovery_reject_unverified_mappings(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    raw = _map()
    with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
        project_repository(repo, raw)  # type: ignore[arg-type]
    with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
        discover_repository_sources(repo, raw)  # type: ignore[arg-type]


def test_verified_capability_does_not_survive_copy_replace_construction_or_pickle() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = load_ontology(root / "ontology")
    forged_decoded = dict(bundle.decoded)
    forged_decoded["projection-map.json"] = _map()

    def assert_forged_copies_are_rejected(verified: OntologyBundle) -> None:
        candidates = (
            replace(verified, decoded=forged_decoded),
            copy.copy(verified),
            copy.deepcopy(verified),
            OntologyBundle(
                verified.root,
                verified.manifest,
                verified.artifact_lock,
                verified.artifacts,
                forged_decoded,
            ),
            pickle.loads(pickle.dumps(verified)),
        )
        for candidate in candidates:
            with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
                project_repository(root, candidate)
            with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
                discover_repository_sources(root, candidate)

    assert_forged_copies_are_rejected(bundle)
    identity = id(bundle)
    assert identity in artifacts_module._VERIFIED_BUNDLES
    del bundle
    gc.collect()
    assert identity not in artifacts_module._VERIFIED_BUNDLES


@pytest.mark.parametrize(
    "catalog_path",
    [
        "../outside.yaml",
        "/tmp/outside.yaml",
        "data\\relations.yaml",
        "",
        "data//relations.yaml",
        "./data/relations.yaml",
    ],
)
def test_catalog_paths_must_be_canonical_and_contained(tmp_path: Path, catalog_path: str) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path.parent / "outside.yaml"
    outside.write_text("relations:\n- id: should_not_be_ingested\n", encoding="utf-8")
    projection = _map()
    catalogs = cast(list[dict[str, object]], projection["catalogs"])
    catalogs[0]["path"] = catalog_path
    with pytest.raises(OntologyInfrastructureError, match="locator path"):
        _project_repository_with_projection(repo, projection)


@pytest.mark.parametrize("duplicate", ["id", "path"])
def test_duplicate_catalog_declarations_fail_closed(tmp_path: Path, duplicate: str) -> None:
    repo = _repo(tmp_path)
    projection = _map()
    catalogs = cast(list[dict[str, object]], projection["catalogs"])
    if duplicate == "id":
        catalogs.append({"id": "assertions", "path": "data/other.yaml"})
    else:
        catalogs.append({"id": "other", "path": "data/relations.yaml"})
    with pytest.raises(OntologyInfrastructureError, match="Duplicate compiled projection catalog"):
        _project_repository_with_projection(repo, projection)


def test_flat_root_replacement_symlink_is_rejected_before_ingest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    projection = _map()
    original_open = repository_sources_module.os.open
    replaced = False

    def racing_open(path: str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        nonlocal replaced
        if dir_fd is not None and path == "a.yaml" and not replaced:
            target = repo / "data/substances/a.yaml"
            target.unlink()
            target.symlink_to(repo / "data/products/p.yaml")
            replaced = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(repository_sources_module.os, "open", racing_open)
    with pytest.raises(OntologyInfrastructureError, match="Cannot load repository source"):
        from planner.ontology.repository_sources import _discover_repository_sources

        _discover_repository_sources(repo, projection)
    assert replaced


def test_committed_projection_emits_uri_relationships_for_stack_products() -> None:
    root = Path(__file__).resolve().parents[1]
    result = project_repository(root, load_ontology(root / "ontology"))
    product_edges = [triple for triple in result.triples if triple[1].endswith("/slot/product>")]
    assert product_edges
    assert all(triple[2].startswith("<") and triple[2].endswith(">") for triple in product_edges)


@pytest.mark.parametrize("base_iri", [None, "not-an-iri", "https://example.test/ontology"])
def test_projection_requires_explicit_trailing_slash_base_iri(tmp_path: Path, base_iri: object) -> None:
    repo = _repo(tmp_path)
    projection = cast(dict[str, object], _map()["repository_projection"])
    if base_iri is None:
        projection.pop("base_iri", None)
    else:
        projection["base_iri"] = base_iri
    with pytest.raises(OntologyInfrastructureError, match="base_iri"):
        _project_repository_with_projection(repo, {"repository_projection": projection})
