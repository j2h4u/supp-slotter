"""Focused tests for compiled repository discovery and RDF projection."""

from __future__ import annotations

from pathlib import Path

import pytest
from planner.ontology.artifacts import load_ontology
from planner.ontology.errors import OntologyInfrastructureError
from planner.ontology.projection import _project_repository_with_projection, project_repository
from planner.ontology.repository_sources import discover_repository_sources
from rdflib import URIRef

BASE = "https://example.test/ontology/"


def _map() -> dict[str, object]:
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


def test_catalog_ref_selects_declared_catalog_and_does_not_ingest_schedule(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "schedule.yaml").write_text("id: should_not_be_read\n", encoding="utf-8")
    result = _project_repository_with_projection(repo, _map())
    assert any(
        record.source_id == "assertions" and record.field_path == "relations[0].id" for record in result.provenance
    )
    assert not any("should_not_be_read" in triple for triple in result.triples)


def test_unknown_empty_container_fails_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "data/substances/a.yaml").write_text("id: sub_a\nname: A\nunknown: {}\n", encoding="utf-8")
    with pytest.raises(OntologyInfrastructureError, match="unknown"):
        _project_repository_with_projection(repo, _map())


def test_public_projection_and_discovery_reject_unverified_mappings(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    raw = _map()
    with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
        project_repository(repo, raw)  # type: ignore[arg-type]
    with pytest.raises(OntologyInfrastructureError, match="verified OntologyBundle"):
        discover_repository_sources(repo, raw)  # type: ignore[arg-type]


def test_committed_projection_emits_uri_relationships_for_stack_products() -> None:
    root = Path(__file__).resolve().parents[1]
    result = project_repository(root, load_ontology(root / "ontology"))
    product_edges = [triple for triple in result.triples if triple[1].endswith("/product>")]
    assert product_edges
    assert all(triple[2].startswith("<") and triple[2].endswith(">") for triple in product_edges)
